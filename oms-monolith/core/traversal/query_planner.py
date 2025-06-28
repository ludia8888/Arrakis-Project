"""
Query Planner

Intelligent WOQL query planning and optimization for graph traversal operations.
Provides query optimization, caching strategies, and execution planning.
"""

import hashlib
import json
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

from terminusdb_client import WOQLQuery as WQ
from core.traversal.models import TraversalQuery, TraversalDirection


@dataclass
class QueryPlan:
    """Execution plan for a graph traversal query"""
    query_id: str
    woql_query: WQ
    estimated_cost: float
    estimated_results: int
    cache_key: str
    ttl_seconds: int
    optimization_hints: List[str]
    

@dataclass
class QueryStatistics:
    """Statistics for query performance optimization"""
    execution_count: int
    avg_execution_time_ms: float
    avg_result_count: int
    cache_hit_rate: float
    last_executed: datetime


class QueryPlanner:
    """
    Intelligent query planner for TerminusDB WOQL operations.
    
    Capabilities:
    - Query cost estimation
    - Execution plan optimization  
    - Intelligent caching strategies
    - Query pattern recognition
    - Performance monitoring
    """
    
    def __init__(self):
        self._query_stats: Dict[str, QueryStatistics] = {}
        self._plan_cache: Dict[str, QueryPlan] = {}
        self._optimization_rules = self._initialize_optimization_rules()
        
    def create_execution_plan(self, query: TraversalQuery) -> QueryPlan:
        """
        Create optimized execution plan for traversal query.
        
        Analyzes query patterns and applies optimization strategies:
        - Index usage optimization
        - Query rewriting for performance
        - Caching strategy selection
        - Resource estimation
        """
        # Generate unique query fingerprint
        query_fingerprint = self._generate_query_fingerprint(query)
        
        # Check if we have a cached plan
        if query_fingerprint in self._plan_cache:
            cached_plan = self._plan_cache[query_fingerprint]
            if self._is_plan_valid(cached_plan):
                return cached_plan
        
        # Create new execution plan
        plan = self._build_execution_plan(query, query_fingerprint)
        
        # Cache the plan
        self._plan_cache[query_fingerprint] = plan
        
        return plan
    
    def _build_execution_plan(self, query: TraversalQuery, fingerprint: str) -> QueryPlan:
        """Build optimized execution plan for the query"""
        
        # Estimate query cost and selectivity
        cost_estimate = self._estimate_query_cost(query)
        result_estimate = self._estimate_result_count(query)
        
        # Apply optimization rules
        optimized_woql = self._optimize_woql_query(query)
        optimization_hints = self._get_optimization_hints(query)
        
        # Determine caching strategy
        cache_key = self._generate_cache_key(query)
        ttl_seconds = self._calculate_cache_ttl(query, cost_estimate)
        
        return QueryPlan(
            query_id=fingerprint,
            woql_query=optimized_woql,
            estimated_cost=cost_estimate,
            estimated_results=result_estimate,
            cache_key=cache_key,
            ttl_seconds=ttl_seconds,
            optimization_hints=optimization_hints
        )
    
    def _optimize_woql_query(self, query: TraversalQuery) -> WQ:
        """
        Apply optimization rules to WOQL query construction.
        
        Optimization strategies:
        1. Index-aware query ordering
        2. Predicate pushdown
        3. Early termination conditions
        4. Batch processing for large result sets
        """
        woql = WQ()
        
        # Strategy 1: Start with most selective conditions
        if query.filters:
            # Apply filters early to reduce search space
            filter_conditions = []
            for prop, value in query.filters.items():
                if self._is_highly_selective(prop, value):
                    filter_conditions.append(
                        WQ.triple("v:node", f"@schema:{prop}", WQ.string(str(value)))
                    )
            
            if filter_conditions:
                woql = woql.and_(*filter_conditions)
        
        # Strategy 2: Optimize path traversal based on direction and depth
        if query.max_depth == 1:
            # Direct relationship - no path() needed
            for start_node in query.start_nodes:
                for relation in query.relations:
                    if query.direction == TraversalDirection.OUTBOUND:
                        woql = woql.triple(
                            WQ.string(start_node), 
                            f"@schema:{relation}", 
                            "v:target"
                        )
                    elif query.direction == TraversalDirection.INBOUND:
                        woql = woql.triple(
                            "v:target", 
                            f"@schema:{relation}", 
                            WQ.string(start_node)
                        )
        else:
            # Multi-hop traversal - use optimized path queries
            woql = self._build_optimized_path_query(query)
        
        # Strategy 3: Add result limiting and ordering
        if query.limit:
            woql = woql.limit(query.limit)
            
        # Strategy 4: Select only required fields
        select_vars = ["v:target", "v:target_type", "v:target_label"]
        if query.include_metadata:
            select_vars.extend(["v:created", "v:modified"])
            
        woql = woql.select(*select_vars)
        
        return woql
    
    def _build_optimized_path_query(self, query: TraversalQuery) -> WQ:
        """Build optimized path query for multi-hop traversal"""
        
        # Determine optimal path pattern
        if len(query.relations) == 1:
            relation_pattern = f"@schema:{query.relations[0]}"
        else:
            # Multiple relations - create optimized union
            patterns = []
            for rel in query.relations:
                # Prioritize relations by selectivity
                selectivity = self._get_relation_selectivity(rel)
                patterns.append((f"@schema:{rel}", selectivity))
            
            # Sort by selectivity (most selective first)
            patterns.sort(key=lambda x: x[1])
            relation_pattern = "(" + "|".join([p[0] for p in patterns]) + ")"
        
        # Add direction modifier
        if query.direction == TraversalDirection.BIDIRECTIONAL:
            relation_pattern += f"|^{relation_pattern}"
        elif query.direction == TraversalDirection.INBOUND:
            relation_pattern = f"^{relation_pattern}"
        
        # Add depth modifier with optimization
        if query.max_depth <= 3:
            depth_modifier = "+"  # 1 or more - efficient for short paths
        else:
            depth_modifier = "*"  # 0 or more - handles longer paths
        
        # Build path queries for each start node
        path_queries = []
        for start_node in query.start_nodes:
            path_query = WQ.path(
                WQ.string(start_node),
                relation_pattern + depth_modifier,
                "v:target"
            ).triple("v:target", "rdf:type", "v:target_type")
             .triple("v:target", "rdfs:label", "v:target_label")
            
            path_queries.append(path_query)
        
        # Combine multiple start nodes efficiently
        if len(path_queries) == 1:
            return path_queries[0]
        else:
            return WQ.or_(*path_queries)
    
    def _estimate_query_cost(self, query: TraversalQuery) -> float:
        """Estimate computational cost of the query"""
        base_cost = 1.0
        
        # Factor in traversal depth (exponential cost growth)
        depth_factor = query.max_depth ** 1.5
        
        # Factor in number of start nodes
        start_nodes_factor = len(query.start_nodes) * 0.5
        
        # Factor in number of relations (affects branching)
        relations_factor = len(query.relations) * 0.3
        
        # Factor in direction (bidirectional is more expensive)
        direction_factor = 2.0 if query.direction == TraversalDirection.BIDIRECTIONAL else 1.0
        
        # Factor in filters (reduce cost if highly selective)
        filter_factor = 1.0
        if query.filters:
            selectivity = sum(self._is_highly_selective(k, v) for k, v in query.filters.items())
            filter_factor = max(0.1, 1.0 - (selectivity * 0.3))
        
        total_cost = (
            base_cost * 
            depth_factor * 
            start_nodes_factor * 
            relations_factor * 
            direction_factor * 
            filter_factor
        )
        
        return round(total_cost, 2)
    
    def _estimate_result_count(self, query: TraversalQuery) -> int:
        """Estimate number of results the query will return"""
        
        # Base estimate from historical data
        base_estimate = self._get_historical_result_count(query)
        
        if base_estimate is None:
            # No historical data - use heuristics
            base_estimate = 100  # Default estimate
            
            # Adjust based on depth
            depth_multiplier = min(query.max_depth * 2, 10)
            base_estimate *= depth_multiplier
            
            # Adjust based on number of start nodes
            base_estimate *= len(query.start_nodes)
            
            # Apply filters
            if query.filters:
                selectivity_reduction = len(query.filters) * 0.3
                base_estimate = int(base_estimate * (1 - selectivity_reduction))
        
        # Apply limit if specified
        if query.limit and query.limit < base_estimate:
            return query.limit
            
        return max(1, base_estimate)
    
    def _calculate_cache_ttl(self, query: TraversalQuery, cost: float) -> int:
        """Calculate appropriate cache TTL based on query characteristics"""
        
        # Base TTL - expensive queries cached longer
        base_ttl = self.config.cache.query_cache_ttl
        
        if cost > 10.0:
            return base_ttl * 4  # 20 minutes for expensive queries
        elif cost > 5.0:
            return base_ttl * 2  # 10 minutes for moderate queries
        else:
            return base_ttl  # 5 minutes for cheap queries
    
    def _get_optimization_hints(self, query: TraversalQuery) -> List[str]:
        """Generate optimization hints for the query"""
        hints = []
        
        if query.max_depth > self.config.traversal.default_traversal_depth:
            hints.append("Consider reducing max_depth for better performance")
            
        if len(query.start_nodes) > self.config.traversal.max_entities_to_analyze:
            hints.append("Large number of start nodes - consider batch processing")
            
        if not query.filters and query.max_depth > self.config.traversal.critical_path_threshold:
            hints.append("Add filters to reduce search space for deep traversals")
            
        if query.direction == TraversalDirection.BIDIRECTIONAL and query.max_depth > self.config.traversal.critical_path_threshold:
            hints.append("Bidirectional deep traversal is expensive - consider separate queries")
            
        return hints
    
    def _generate_query_fingerprint(self, query: TraversalQuery) -> str:
        """Generate unique fingerprint for query caching"""
        query_dict = {
            'start_nodes': sorted(query.start_nodes),
            'relations': sorted(query.relations),
            'direction': query.direction.value,
            'max_depth': query.max_depth,
            'limit': query.limit,
            'filters': dict(sorted(query.filters.items())),
            'include_metadata': query.include_metadata
        }
        
        query_json = json.dumps(query_dict, sort_keys=True)
        return hashlib.md5(query_json.encode()).hexdigest()
    
    def _generate_cache_key(self, query: TraversalQuery) -> str:
        """Generate cache key for query results"""
        return f"traversal:{self._generate_query_fingerprint(query)}"
    
    def _is_plan_valid(self, plan: QueryPlan) -> bool:
        """Check if cached execution plan is still valid"""
        try:
            from datetime import datetime, timedelta
            
            # Check plan age
            plan_age = datetime.utcnow() - plan.created_at
            max_age = timedelta(hours=self.config.traversal.query_plan_validation_timeout_hours)
            
            if plan_age > max_age:
                return False
            
            # Check if estimated cost is still reasonable
            if plan.estimated_cost > 100.0:  # Very expensive queries expire faster
                return plan_age < timedelta(minutes=30)
            
            # Check if plan has optimization hints that suggest it's inefficient
            if len(plan.optimization_hints) > 3:
                return plan_age < timedelta(hours=1)
            
            return True
            
        except Exception:
            # If we can't validate, assume invalid for safety
            return False
    
    def _initialize_optimization_rules(self) -> Dict[str, Any]:
        """Initialize query optimization rules"""
        return {
            'highly_selective_properties': ['id', 'uuid', 'unique_identifier'],
            'relation_selectivity': {
                'depends_on': 0.3,
                'extends': 0.5,
                'references': 0.7,
                'related_to': 0.9
            }
        }
    
    def _is_highly_selective(self, property_name: str, value: Any) -> bool:
        """Check if a property filter is highly selective"""
        return property_name in self._optimization_rules['highly_selective_properties']
    
    def _get_relation_selectivity(self, relation: str) -> float:
        """Get selectivity score for a relation (lower = more selective)"""
        return self._optimization_rules['relation_selectivity'].get(relation, 0.5)
    
    def _get_historical_result_count(self, query: TraversalQuery) -> Optional[int]:
        """Get historical result count for similar queries"""
        fingerprint = self._generate_query_fingerprint(query)
        if fingerprint in self._query_stats:
            return self._query_stats[fingerprint].avg_result_count
        return None
    
    def record_execution_stats(
        self, 
        plan: QueryPlan, 
        execution_time_ms: float, 
        result_count: int,
        cache_hit: bool = False
    ):
        """Record execution statistics for query optimization"""
        query_id = plan.query_id
        
        if query_id not in self._query_stats:
            self._query_stats[query_id] = QueryStatistics(
                execution_count=0,
                avg_execution_time_ms=0.0,
                avg_result_count=0,
                cache_hit_rate=0.0,
                last_executed=datetime.utcnow()
            )
        
        stats = self._query_stats[query_id]
        
        # Update running averages
        stats.execution_count += 1
        stats.avg_execution_time_ms = (
            (stats.avg_execution_time_ms * (stats.execution_count - 1) + execution_time_ms) / 
            stats.execution_count
        )
        stats.avg_result_count = (
            (stats.avg_result_count * (stats.execution_count - 1) + result_count) / 
            stats.execution_count
        )
        
        # Update cache hit rate
        if cache_hit:
            cache_hits = stats.cache_hit_rate * (stats.execution_count - 1) + 1
            stats.cache_hit_rate = cache_hits / stats.execution_count
        else:
            cache_hits = stats.cache_hit_rate * (stats.execution_count - 1)
            stats.cache_hit_rate = cache_hits / stats.execution_count
            
        stats.last_executed = datetime.utcnow()
    
    def get_query_performance_report(self) -> Dict[str, Any]:
        """Generate performance report for query optimization analysis"""
        total_queries = len(self._query_stats)
        if total_queries == 0:
            return {"message": "No query statistics available"}
        
        avg_execution_time = sum(s.avg_execution_time_ms for s in self._query_stats.values()) / total_queries
        avg_cache_hit_rate = sum(s.cache_hit_rate for s in self._query_stats.values()) / total_queries
        
        # Find slowest queries
        slowest_queries = sorted(
            self._query_stats.items(),
            key=lambda x: x[1].avg_execution_time_ms,
            reverse=True
        )[:5]
        
        return {
            "total_unique_queries": total_queries,
            "average_execution_time_ms": round(avg_execution_time, 2),
            "average_cache_hit_rate": round(avg_cache_hit_rate, 3),
            "slowest_queries": [
                {
                    "query_id": qid,
                    "avg_execution_time_ms": stats.avg_execution_time_ms,
                    "execution_count": stats.execution_count
                }
                for qid, stats in slowest_queries
            ]
        }