"""
GraphQL WebSocket Service - Handles real-time subscriptions
This service focuses on WebSocket connections and GraphQL subscriptions.
For HTTP GraphQL queries/mutations, use modular_main.py
"""

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Removed dangerous create_scope_rbac_middleware import

# shared 모듈 import를 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.graphql.auth import (
    AuthenticationManager,
    GraphQLWebSocketAuth,
    get_current_user_optional,
)
from core.auth_utils import UserContext

from .realtime_publisher import realtime_publisher
from .websocket_manager import websocket_manager

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
auth_manager: Optional[AuthenticationManager] = None
graphql_ws_auth: Optional[GraphQLWebSocketAuth] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Execute on startup
    global auth_manager, graphql_ws_auth
    logger.info("GraphQL Service starting...")

    try:
        # Initialize Authentication Manager
        auth_manager = AuthenticationManager()
        await auth_manager.init_redis()
        logger.info("Authentication manager initialized")

        # Initialize GraphQL WebSocket authentication
        graphql_ws_auth = GraphQLWebSocketAuth(auth_manager)
        logger.info("GraphQL WebSocket authentication initialized")

        # Initialize NATS connection
        await realtime_publisher.connect()
        logger.info("Connected to NATS for real-time events")
    except Exception as e:
        logger.warning(f"Failed to connect to NATS: {e}")

    yield

    # Execute on shutdown
    logger.info("GraphQL Service shutting down gracefully...")

    try:
        # 1. Clean up WebSocket connections
        logger.info("Cleaning up WebSocket connections...")
        websocket_manager.stop_background_tasks()

        # 2. Disconnect from NATS
        logger.info("Disconnecting from NATS...")
        await realtime_publisher.disconnect()

        # 3. Clean up Authentication Manager
        if auth_manager:
            logger.info("Closing authentication manager...")
            await auth_manager.close()

        # 4. Stop new GraphQL requests
        logger.info("Stopping new GraphQL requests...")

        # 5. Wait for ongoing GraphQL queries to complete
        logger.info("Waiting for GraphQL queries to complete...")
        await asyncio.sleep(1)  # Short wait time

        logger.info("GraphQL Service shutdown completed gracefully")
    except Exception as e:
        logger.error(f"Error during graceful shutdown: {e}")
        raise


app = FastAPI(
    title="OMS GraphQL WebSocket Service",
    description="WebSocket service for GraphQL subscriptions",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add RBAC middleware - using actual ScopeRBACMiddleware
from core.iam.scope_rbac_middleware import ScopeRBACMiddleware

app.add_middleware(
    ScopeRBACMiddleware,
    config={"public_paths": ["/health", "/", "/graphql", "/ws", "/schema"]},
)


# Remove GraphQL router - this service only handles WebSocket connections
# For GraphQL HTTP endpoints, use modular_main.py


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "graphql-service", "version": "1.0.0"}


@app.get("/")
async def root():
    """Root endpoint - GraphQL endpoint guide"""
    return {
        "message": "OMS GraphQL Service",
        "graphql_endpoint": "/graphql",
        "graphiql_endpoint": "/graphql",
        "documentation": "Visit /graphql in your browser to access GraphQL Playground",
    }


@app.get("/schema")
async def get_schema():
    """WebSocket subscription info"""
    return {
        "service": "websocket-only",
        "subscriptions": ["object_type_updates"],
        "note": "For GraphQL schema, use the HTTP endpoint on port 8006",
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint - GraphQL Subscriptions

    P3 Event-Driven: WebSocket-based real-time event streaming
    P4 Cache-First: Connection pooling and efficient management
    """
    # Perform WebSocket authentication
    user_context = None
    if graphql_ws_auth:
        try:
            user_context = await graphql_ws_auth.authenticate_graphql_subscription(
                websocket
            )
            if user_context:
                logger.info(f"WebSocket authenticated: {user_context.username}")
        except Exception as e:
            logger.error(f"WebSocket authentication failed: {e}")
            await websocket.close(code=1008, reason="Authentication failed")
            return
    else:
        logger.warning(
            "GraphQL WebSocket authentication not initialized, "
            "allowing anonymous connection"
        )
        await websocket.accept()

    connection = None
    try:
        # Accept and register WebSocket connection (pass user_context as user)
        connection = await websocket_manager.connect(websocket, user_context)
        logger.info(f"WebSocket connection established: {connection.connection_id}")

        # Send welcome message
        await connection.send_message(
            {
                "type": "connection_ack",
                "connection_id": connection.connection_id,
                "message": "WebSocket connection established for GraphQL subscriptions",
            }
        )

        # Message processing loop
        while True:
            try:
                # Receive client message
                data = await websocket.receive_text()
                message = json.loads(data) if data else {}

                connection.messages_received += 1
                message_type = message.get("type", "")

                if message_type == "ping":
                    # Ping response
                    connection.update_last_ping()
                    await connection.send_message(
                        {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                    )

                elif message_type == "pong":
                    # Pong received
                    connection.update_last_ping()

                elif message_type == "subscription_start":
                    # Start subscription - includes permission check
                    subscription_id = message.get("subscription_id")
                    subscription_name = message.get("subscription_name", "")
                    variables = message.get("variables", {})

                    if subscription_id:
                        # Only authenticated users check subscription permissions
                        if user_context and graphql_ws_auth:
                            authorized = await graphql_ws_auth.authorize_subscription(
                                user_context, subscription_name, variables
                            )
                            if not authorized:
                                await connection.send_message(
                                    {
                                        "type": "subscription_error",
                                        "subscription_id": subscription_id,
                                        "message": "Insufficient permissions for this subscription",
                                    }
                                )
                                continue

                        websocket_manager.add_subscription(
                            connection.connection_id, subscription_id
                        )
                        await connection.send_message(
                            {
                                "type": "subscription_ack",
                                "subscription_id": subscription_id,
                            }
                        )

                elif message_type == "subscription_stop":
                    # Stop subscription
                    subscription_id = message.get("subscription_id")
                    if subscription_id:
                        websocket_manager.remove_subscription(
                            connection.connection_id, subscription_id
                        )
                        await connection.send_message(
                            {
                                "type": "subscription_complete",
                                "subscription_id": subscription_id,
                            }
                        )

            except WebSocketDisconnect:
                logger.info(
                    f"WebSocket client disconnected: {connection.connection_id}"
                )
                break
            except json.JSONDecodeError:
                await connection.send_message(
                    {"type": "error", "message": "Invalid JSON format"}
                )
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                await connection.send_message(
                    {"type": "error", "message": "Internal server error"}
                )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected during connection setup")
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        # Clean up connection
        if connection:
            await websocket_manager.disconnect(connection.connection_id)


@app.get("/ws/stats")
async def websocket_stats():
    """WebSocket connection statistics"""
    return websocket_manager.get_statistics()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8004)
