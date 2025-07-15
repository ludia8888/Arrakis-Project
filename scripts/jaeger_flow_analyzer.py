#!/usr/bin/env python3
"""
Production-ready Jaeger flow visualization and service dependency analyzer.
Generates real-time call graphs, dependency maps, and flow visualizations.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import aiohttp
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.offline as pyo
import seaborn as sns
from plotly.subplots import make_subplots

# Configure logging
logging.basicConfig(
    level = logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class JaegerFlowAnalyzer:
    """Analyze Jaeger traces to generate service dependency maps and flow visualizations."""

    ARRAKIS_SERVICES = {
        'ontology-management-service',
        'user-service',
        'audit-service',
        'data-kernel-service',
        'embedding-service',
        'scheduler-service',
        'event-gateway'
    }

    def __init__(self, jaeger_url: str = 'http://localhost:16686',
                 output_dir: str = 'docs/jaeger-analysis'):
        self.jaeger_url = jaeger_url.rstrip('/')
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents = True, exist_ok = True)

        # Analysis cache
        self.traces_cache = {}
        self.dependency_graph = nx.DiGraph()
        self.service_metrics = defaultdict(lambda: defaultdict(list))

        # Color scheme for visualizations
        self.service_colors = {
            'ontology-management-service': '#FF6B6B',
            'user-service': '#4ECDC4',
            'audit-service': '#45B7D1',
            'data-kernel-service': '#FFA07A',
            'embedding-service': '#98D8C8',
            'scheduler-service': '#F7DC6F',
            'event-gateway': '#BB8FCE'
        }

    async def analyze_traces(self, time_range: str = '1h',
                           operation_filter: str = None) -> Dict:
        """Analyze traces from Jaeger and generate comprehensive flow analysis."""
        logger.info(f"Starting Jaeger trace analysis for {time_range}")

        # Fetch traces
        traces = await self._fetch_traces(time_range, operation_filter)

        if not traces:
            logger.warning("No traces found for the specified time range")
            return {}

        logger.info(f"Analyzing {len(traces)} traces...")

        # Process traces
        analysis_results = {
            'metadata': {
                'timestamp': datetime.utcnow().isoformat(),
                'time_range': time_range,
                'trace_count': len(traces),
                'operation_filter': operation_filter
            },
            'service_dependencies': self._analyze_service_dependencies(traces),
            'flow_patterns': self._analyze_flow_patterns(traces),
            'performance_metrics': self._analyze_performance_metrics(traces),
            'error_analysis': self._analyze_errors(traces),
            'hotpaths': self._identify_hotpaths(traces),
            'anomalies': self._detect_anomalies(traces)
        }

        # Generate visualizations
        await self._generate_visualizations(analysis_results)

        # Save analysis results
        results_file = self.output_dir / f'analysis_results_{int(datetime.utcnow().timestamp())}.json'
        with open(results_file, 'w') as f:
            json.dump(analysis_results, f, indent = 2, default = str)

        logger.info(f"Analysis complete. Results saved to {results_file}")

        return analysis_results

    async def _fetch_traces(self, time_range: str, operation_filter: str) -> List[Dict]:
        """Fetch traces from Jaeger API."""
        logger.info("Fetching traces from Jaeger...")

        # Parse time range
        lookback_ms = self._parse_time_range(time_range)
        end_time = int(datetime.utcnow().timestamp() * 1000000)  # microseconds
        start_time = end_time - (lookback_ms * 1000)  # convert to microseconds

        traces = []

        async with aiohttp.ClientSession() as session:
            # Fetch traces for each service
            for service in self.ARRAKIS_SERVICES:
                try:
                    params = {
                        'service': service,
                        'start': start_time,
                        'end': end_time,
                        'limit': 1000  # Limit per service
                    }

                    if operation_filter:
                        params['operation'] = operation_filter

                    url = f"{self.jaeger_url}/api/traces"

                    async with session.get(url, params = params) as response:
                        if response.status == 200:
                            data = await response.json()
                            if 'data' in data:
                                traces.extend(data['data'])
                                logger.info(f"Fetched {len(data['data'])} traces for {service}")
                        else:
                            logger.warning(f"Failed to fetch traces for {service}: {response.status}")

                except Exception as e:
                    logger.error(f"Error fetching traces for {service}: {e}")

        return traces

    def _parse_time_range(self, time_range: str) -> int:
        """Parse time range string to milliseconds."""
        time_range = time_range.lower()

        if time_range.endswith('m'):
            return int(time_range[:-1]) * 60 * 1000
        elif time_range.endswith('h'):
            return int(time_range[:-1]) * 60 * 60 * 1000
        elif time_range.endswith('d'):
            return int(time_range[:-1]) * 24 * 60 * 60 * 1000
        else:
            # Default to minutes
            return int(time_range) * 60 * 1000

    def _analyze_service_dependencies(self, traces: List[Dict]) -> Dict:
        """Analyze service dependencies from traces."""
        logger.info("Analyzing service dependencies...")

        dependencies = defaultdict(lambda: defaultdict(int))
        call_patterns = defaultdict(list)

        for trace in traces:
            spans = trace.get('spans', [])

            # Build call hierarchy
            span_by_id = {span['spanID']: span for span in spans}

            for span in spans:
                span_service = span.get('process', {}).get('serviceName', 'unknown')

                # Find parent span
                if span.get('references'):
                    for ref in span['references']:
                        if ref.get('refType') == 'CHILD_OF':
                            parent_span_id = ref.get('spanID')
                            if parent_span_id in span_by_id:
                                parent_span = span_by_id[parent_span_id]
                                parent_service = parent_span.get('process',
                                    {}).get('serviceName', 'unknown')

                                if parent_service != span_service:
                                    dependencies[parent_service][span_service] += 1
                                    call_patterns[parent_service].append({
                                        'target': span_service,
                                        'operation': span.get('operationName',
                                            'unknown'),
                                        'duration': span.get('duration', 0),
                                        'timestamp': span.get('startTime', 0)
                                    })

        # Convert to regular dict and calculate metrics
        dependency_map = {}
        for source, targets in dependencies.items():
            dependency_map[source] = dict(targets)

        # Calculate dependency metrics
        service_stats = {}
        for service in self.ARRAKIS_SERVICES:
            incoming = sum(deps.get(service, 0) for deps in dependency_map.values())
            outgoing = sum(dependency_map.get(service, {}).values())

            service_stats[service] = {
                'incoming_calls': incoming,
                'outgoing_calls': outgoing,
                'fan_in': len([s for s,
                    deps in dependency_map.items() if service in deps]),
                'fan_out': len(dependency_map.get(service, {}))
            }

        return {
            'dependency_map': dependency_map,
            'call_patterns': dict(call_patterns),
            'service_stats': service_stats,
            'most_called_services': sorted(
                [(service, stats['incoming_calls']) for service,
                    stats in service_stats.items()],
                key = lambda x: x[1],
                reverse = True
            )[:10]
        }

    def _analyze_flow_patterns(self, traces: List[Dict]) -> Dict:
        """Analyze common flow patterns in traces."""
        logger.info("Analyzing flow patterns...")

        flow_patterns = defaultdict(int)
        operation_flows = defaultdict(lambda: defaultdict(int))

        for trace in traces:
            spans = trace.get('spans', [])

            # Extract service flow for this trace
            service_sequence = []
            span_by_start = sorted(spans, key = lambda x: x.get('startTime', 0))

            for span in span_by_start:
                service = span.get('process', {}).get('serviceName', 'unknown')
                operation = span.get('operationName', 'unknown')

                if service in self.ARRAKIS_SERVICES:
                    service_sequence.append(service)
                    operation_flows[service][operation] += 1

            # Record flow pattern
            if len(service_sequence) > 1:
                flow_key = ' -> '.join(service_sequence[:5])  # Limit to first 5 services
                flow_patterns[flow_key] += 1

        # Find most common patterns
        common_patterns = sorted(flow_patterns.items(), key = lambda x: x[1],
            reverse = True)[:20]

        return {
            'common_patterns': common_patterns,
            'operation_distribution': dict(operation_flows),
            'pattern_count': len(flow_patterns),
            'unique_flows': len(flow_patterns)
        }

    def _analyze_performance_metrics(self, traces: List[Dict]) -> Dict:
        """Analyze performance metrics from traces."""
        logger.info("Analyzing performance metrics...")

        service_durations = defaultdict(list)
        operation_durations = defaultdict(list)
        error_rates = defaultdict(lambda: {'total': 0, 'errors': 0})

        for trace in traces:
            spans = trace.get('spans', [])

            for span in spans:
                service = span.get('process', {}).get('serviceName', 'unknown')
                operation = span.get('operationName', 'unknown')
                duration = span.get('duration', 0) / 1000  # Convert to milliseconds

                if service in self.ARRAKIS_SERVICES:
                    service_durations[service].append(duration)
                    operation_durations[f"{service}.{operation}"].append(duration)

                    # Check for errors
                    error_rates[service]['total'] += 1
                    if self._span_has_error(span):
                        error_rates[service]['errors'] += 1

        # Calculate statistics
        service_stats = {}
        for service, durations in service_durations.items():
            if durations:
                stats = {
                    'count': len(durations),
                    'mean_duration': sum(durations) / len(durations),
                    'p50_duration': sorted(durations)[len(durations) // 2],
                    'p95_duration': sorted(durations)[int(len(durations) * 0.95)],
                    'p99_duration': sorted(durations)[int(len(durations) * 0.99)],
                    'max_duration': max(durations),
                    'min_duration': min(durations)
                }

                # Add error rate
                error_data = error_rates[service]
                if error_data['total'] > 0:
                    stats['error_rate'] = error_data['errors'] / error_data['total']
                else:
                    stats['error_rate'] = 0

                service_stats[service] = stats

        # Top slow operations
        slow_operations = []
        for operation, durations in operation_durations.items():
            if durations and len(durations) >= 5:  # Minimum sample size
                slow_operations.append((
                    operation,
                    sum(durations) / len(durations),
                    max(durations),
                    len(durations)
                ))

        slow_operations.sort(key = lambda x: x[1], reverse = True)

        return {
            'service_performance': service_stats,
            'slow_operations': slow_operations[:20],
            'error_rates': dict(error_rates)
        }

    def _span_has_error(self, span: Dict) -> bool:
        """Check if a span has error indicators."""
        tags = span.get('tags', [])

        for tag in tags:
            if tag.get('key') == 'error' and tag.get('value') is True:
                return True
            if tag.get('key') == 'http.status_code':
                status_code = tag.get('value')
                if isinstance(status_code, (int, str)) and int(status_code) >= 400:
                    return True

        return False

    def _analyze_errors(self, traces: List[Dict]) -> Dict:
        """Analyze errors and failures in traces."""
        logger.info("Analyzing errors...")

        error_patterns = defaultdict(int)
        service_errors = defaultdict(list)
        error_sequences = defaultdict(int)

        for trace in traces:
            spans = trace.get('spans', [])
            trace_errors = []

            for span in spans:
                service = span.get('process', {}).get('serviceName', 'unknown')

                if self._span_has_error(span):
                    operation = span.get('operationName', 'unknown')
                    error_info = {
                        'service': service,
                        'operation': operation,
                        'timestamp': span.get('startTime', 0),
                        'duration': span.get('duration', 0),
                        'tags': span.get('tags', [])
                    }

                    service_errors[service].append(error_info)
                    error_patterns[f"{service}.{operation}"] += 1
                    trace_errors.append(service)

            # Record error sequences
            if trace_errors:
                error_sequence = ' -> '.join(trace_errors)
                error_sequences[error_sequence] += 1

        # Find most problematic services
        error_counts = defaultdict(int)
        for service, errors in service_errors.items():
            error_counts[service] = len(errors)

        most_errors = sorted(error_counts.items(), key = lambda x: x[1], reverse = True)

        return {
            'error_patterns': dict(error_patterns),
            'service_errors': dict(service_errors),
            'error_sequences': dict(error_sequences),
            'most_problematic_services': most_errors,
            'total_errors': sum(error_counts.values())
        }

    def _identify_hotpaths(self, traces: List[Dict]) -> Dict:
        """Identify hot paths and critical flows."""
        logger.info("Identifying hot paths...")

        path_frequencies = defaultdict(int)
        path_durations = defaultdict(list)
        critical_paths = []

        for trace in traces:
            spans = trace.get('spans', [])

            # Build trace path
            trace_services = []
            total_duration = 0

            for span in sorted(spans, key = lambda x: x.get('startTime', 0)):
                service = span.get('process', {}).get('serviceName', 'unknown')
                if service in self.ARRAKIS_SERVICES:
                    trace_services.append(service)
                    total_duration += span.get('duration', 0)

            if len(trace_services) >= 2:
                path_key = ' -> '.join(trace_services)
                path_frequencies[path_key] += 1
                path_durations[path_key].append(total_duration / 1000)  # Convert to ms

        # Calculate hot paths
        for path, frequency in path_frequencies.items():
            if frequency >= 5:  # Minimum frequency threshold
                durations = path_durations[path]
                avg_duration = sum(durations) / len(durations)

                critical_paths.append({
                    'path': path,
                    'frequency': frequency,
                    'avg_duration': avg_duration,
                    'total_duration': sum(durations),
                    'services_count': len(path.split(' -> '))
                })

        # Sort by frequency and duration
        critical_paths.sort(key = lambda x: (x['frequency'], x['avg_duration']),
            reverse = True)

        return {
            'hot_paths': critical_paths[:20],
            'path_frequencies': dict(path_frequencies),
            'most_frequent_paths': sorted(path_frequencies.items(), key = lambda x: x[1],

                reverse = True)[:10]
        }

    def _detect_anomalies(self, traces: List[Dict]) -> Dict:
        """Detect anomalous patterns in traces."""
        logger.info("Detecting anomalies...")

        service_durations = defaultdict(list)
        unusual_patterns = []

        # Collect duration data
        for trace in traces:
            spans = trace.get('spans', [])

            for span in spans:
                service = span.get('process', {}).get('serviceName', 'unknown')
                duration = span.get('duration', 0) / 1000  # Convert to ms

                if service in self.ARRAKIS_SERVICES:
                    service_durations[service].append(duration)

        # Detect duration anomalies using simple statistical methods
        anomalies = {}
        for service, durations in service_durations.items():
            if len(durations) >= 10:  # Minimum sample size
                sorted_durations = sorted(durations)
                q1 = sorted_durations[len(durations) // 4]
                q3 = sorted_durations[3 * len(durations) // 4]
                iqr = q3 - q1

                # Outlier detection
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr

                outliers = [d for d in durations if d < lower_bound or d > upper_bound]

                if outliers:
                    anomalies[service] = {
                        'outlier_count': len(outliers),
                        'outlier_percentage': len(outliers) / len(durations) * 100,
                        'max_outlier': max(outliers),
                        'normal_range': (lower_bound, upper_bound)
                    }

        return {
            'duration_anomalies': anomalies,
            'unusual_patterns': unusual_patterns
        }

    async def _generate_visualizations(self, analysis_results: Dict):
        """Generate comprehensive visualizations."""
        logger.info("Generating visualizations...")

        viz_dir = self.output_dir / 'visualizations'
        viz_dir.mkdir(exist_ok = True)

        # Generate dependency graph
        await self._generate_dependency_graph(
            analysis_results['service_dependencies'], viz_dir
        )

        # Generate performance dashboard
        await self._generate_performance_dashboard(
            analysis_results['performance_metrics'], viz_dir
        )

        # Generate flow visualization
        await self._generate_flow_visualization(
            analysis_results['flow_patterns'], viz_dir
        )

        # Generate error analysis
        await self._generate_error_visualization(
            analysis_results['error_analysis'], viz_dir
        )

        # Generate interactive dashboard
        await self._generate_interactive_dashboard(analysis_results, viz_dir)

    async def _generate_dependency_graph(self, dependencies: Dict, output_dir: Path):
        """Generate service dependency graph visualization."""
        logger.info("Generating dependency graph...")

        # Create NetworkX graph
        G = nx.DiGraph()

        # Add nodes for all services
        for service in self.ARRAKIS_SERVICES:
            G.add_node(service)

        # Add edges from dependency map
        dependency_map = dependencies.get('dependency_map', {})
        for source, targets in dependency_map.items():
            for target, count in targets.items():
                if source in self.ARRAKIS_SERVICES and target in self.ARRAKIS_SERVICES:
                    G.add_edge(source, target, weight = count)

        # Generate static visualization with matplotlib
        plt.figure(figsize=(16, 12))

        # Use circular layout for better visibility
        pos = nx.circular_layout(G)

        # Draw nodes
        node_colors = [self.service_colors.get(node, '#CCCCCC') for node in G.nodes()]
        nx.draw_networkx_nodes(G, pos, node_color = node_colors,
                              node_size = 3000, alpha = 0.8)

        # Draw edges with varying thickness based on call count
        edges = G.edges(data = True)
        for edge in edges:
            source, target, data = edge
            weight = data.get('weight', 1)
            # Normalize weight for edge thickness
            thickness = min(weight / 10, 5)  # Max thickness of 5
            nx.draw_networkx_edges(G, pos, [(source, target)],
                                 width = thickness, alpha = 0.6, edge_color='gray')

        # Draw labels
        nx.draw_networkx_labels(G, pos, font_size = 10, font_weight='bold')

        # Add edge labels for call counts
        edge_labels = {(u, v): str(d['weight']) for u, v, d in G.edges(data = True)}
        nx.draw_networkx_edge_labels(G, pos, edge_labels, font_size = 8)

        plt.title('Service Dependency Graph', fontsize = 16, fontweight='bold')
        plt.axis('of')
        plt.tight_layout()

        # Save static graph
        plt.savefig(output_dir / 'dependency_graph.png', dpi = 300, bbox_inches='tight')
        plt.close()

        # Generate interactive graph with Plotly
        self._generate_interactive_dependency_graph(G, output_dir)

    def _generate_interactive_dependency_graph(self, G: nx.DiGraph, output_dir: Path):
        """Generate interactive dependency graph with Plotly."""

        # Get layout positions
        pos = nx.spring_layout(G, k = 3, iterations = 50)

        # Prepare node trace
        node_x = []
        node_y = []
        node_text = []
        node_colors = []

        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            node_text.append(node)
            node_colors.append(self.service_colors.get(node, '#CCCCCC'))

        node_trace = go.Scatter(
            x = node_x, y = node_y,
            mode='markers+text',
            text = node_text,
            textposition='middle center',
            textfont = dict(size = 12, color='white'),
            marker = dict(
                size = 50,
                color = node_colors,
                line = dict(width = 2, color='white')
            ),
            hovertemplate='<b>%{text}</b><extra></extra>',
            name='Services'
        )

        # Prepare edge traces
        edge_x = []
        edge_y = []
        edge_info = []

        for edge in G.edges(data = True):
            source, target, data = edge
            x0, y0 = pos[source]
            x1, y1 = pos[target]

            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
            edge_info.append(f"{source} → {target}: {data.get('weight', 1)} calls")

        edge_trace = go.Scatter(
            x = edge_x, y = edge_y,
            line = dict(width = 2, color='#888'),
            hoverinfo='none',
            mode='lines',
            name='Dependencies'
        )

        # Create figure
        fig = go.Figure(data=[edge_trace, node_trace],
                       layout = go.Layout(
                           title='Interactive Service Dependency Graph',
                           titlefont_size = 16,
                           showlegend = False,
                           hovermode='closest',
                           margin = dict(b = 20,l = 5,r = 5,t = 40),
                           annotations=[ dict(
                               text="Service dependencies based on Jaeger traces",
                               showarrow = False,
                               xref="paper", yref="paper",
                               x = 0.005, y=-0.002,
                               xanchor='left', yanchor='bottom',
                               font = dict(color='#888', size = 12)
                           )],
                           xaxis = dict(showgrid = False, zeroline = False,
                               showticklabels = False),
                           yaxis = dict(showgrid = False, zeroline = False,
                               showticklabels = False)
                       ))

        # Save interactive graph
        pyo.plot(fig, filename = str(output_dir / 'dependency_graph_interactive.html'),
                auto_open = False)

    async def _generate_performance_dashboard(self, performance: Dict,
        output_dir: Path):
        """Generate performance metrics dashboard."""
        logger.info("Generating performance dashboard...")

        service_performance = performance.get('service_performance', {})

        if not service_performance:
            logger.warning("No performance data available")
            return

        # Create subplots
        fig = make_subplots(
            rows = 2, cols = 2,
            subplot_titles=('Average Response Time', 'P95 Response Time',
                          'Error Rates', 'Request Counts'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}]]
        )

        services = list(service_performance.keys())
        avg_durations = [service_performance[s]['mean_duration'] for s in services]
        p95_durations = [service_performance[s]['p95_duration'] for s in services]
        error_rates = [service_performance[s]['error_rate'] * 100 for s in services]
        request_counts = [service_performance[s]['count'] for s in services]

        colors = [self.service_colors.get(s, '#CCCCCC') for s in services]

        # Average response time
        fig.add_trace(
            go.Bar(x = services, y = avg_durations, name='Avg Response Time',
                   marker_color = colors),
            row = 1, col = 1
        )

        # P95 response time
        fig.add_trace(
            go.Bar(x = services, y = p95_durations, name='P95 Response Time',
                   marker_color = colors),
            row = 1, col = 2
        )

        # Error rates
        fig.add_trace(
            go.Bar(x = services, y = error_rates, name='Error Rate %',
                   marker_color = colors),
            row = 2, col = 1
        )

        # Request counts
        fig.add_trace(
            go.Bar(x = services, y = request_counts, name='Request Count',
                   marker_color = colors),
            row = 2, col = 2
        )

        # Update layout
        fig.update_layout(
            title_text="Service Performance Dashboard",
            showlegend = False,
            height = 800
        )

        # Update axes labels
        fig.update_yaxes(title_text="Duration (ms)", row = 1, col = 1)
        fig.update_yaxes(title_text="Duration (ms)", row = 1, col = 2)
        fig.update_yaxes(title_text="Error Rate (%)", row = 2, col = 1)
        fig.update_yaxes(title_text="Request Count", row = 2, col = 2)

        # Save dashboard
        pyo.plot(fig, filename = str(output_dir / 'performance_dashboard.html'),
                auto_open = False)

    async def _generate_flow_visualization(self, flow_patterns: Dict, output_dir: Path):
        """Generate flow pattern visualization."""
        logger.info("Generating flow visualization...")

        common_patterns = flow_patterns.get('common_patterns', [])

        if not common_patterns:
            logger.warning("No flow patterns found")
            return

        # Create Sankey diagram for top flows
        top_patterns = common_patterns[:10]  # Top 10 patterns

        # Build Sankey data
        all_services = set()
        links = []

        for pattern, count in top_patterns:
            services = pattern.split(' -> ')
            all_services.update(services)

            # Create links between consecutive services
            for i in range(len(services) - 1):
                links.append({
                    'source': services[i],
                    'target': services[i + 1],
                    'value': count
                })

        # Create node mapping
        service_list = list(all_services)
        service_to_idx = {service: idx for idx, service in enumerate(service_list)}

        # Prepare Sankey diagram
        fig = go.Figure(data=[go.Sankey(
            node = dict(
                pad = 15,
                thickness = 20,
                line = dict(color="black", width = 0.5),
                label = service_list,
                color=[self.service_colors.get(s, '#CCCCCC') for s in service_list]
            ),
            link = dict(
                source=[service_to_idx[link['source']] for link in links],
                target=[service_to_idx[link['target']] for link in links],
                value=[link['value'] for link in links]
            )
        )])

        fig.update_layout(
            title_text="Service Flow Patterns",
            font_size = 12
        )

        # Save flow visualization
        pyo.plot(fig, filename = str(output_dir / 'flow_patterns.html'),
                auto_open = False)

    async def _generate_error_visualization(self, error_analysis: Dict,
        output_dir: Path):
        """Generate error analysis visualization."""
        logger.info("Generating error visualization...")

        service_errors = error_analysis.get('service_errors', {})
        error_patterns = error_analysis.get('error_patterns', {})

        if not service_errors and not error_patterns:
            logger.warning("No error data found")
            return

        # Error distribution by service
        services = []
        error_counts = []

        for service, errors in service_errors.items():
            services.append(service)
            error_counts.append(len(errors))

        fig = go.Figure(data=[
            go.Bar(
                x = services,
                y = error_counts,
                marker_color=[self.service_colors.get(s, '#CCCCCC') for s in services]
            )
        ])

        fig.update_layout(
            title='Error Distribution by Service',
            xaxis_title='Service',
            yaxis_title='Error Count'
        )

        # Save error visualization
        pyo.plot(fig, filename = str(output_dir / 'error_analysis.html'),
                auto_open = False)

    async def _generate_interactive_dashboard(self, analysis_results: Dict,
        output_dir: Path):
        """Generate comprehensive interactive dashboard."""
        logger.info("Generating interactive dashboard...")

        # This would generate a comprehensive HTML dashboard
        # For now, create a summary report

        dashboard_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title > Jaeger Flow Analysis Dashboard</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .metric {{ background: #f5f5f5; padding: 15px; margin: 10px; border-radius: 5px; }}
                .header {{ color: #333; border-bottom: 2px solid #333; }}
            </style>
        </head>
        <body>
            <h1 class="header">Jaeger Flow Analysis Dashboard</h1>

            <div class="metric">
                <h3 > Analysis Summary</h3>
                <p > Generated: {analysis_results['metadata']['timestamp']}</p>
                <p > Time Range: {analysis_results['metadata']['time_range']}</p>
                <p > Traces Analyzed: {analysis_results['metadata']['trace_count']}</p>
            </div>

            <div class="metric">
                <h3 > Service Dependencies</h3>
                <p > Most Called Services:</p>
                <ul>
        """

        for service,
            calls in analysis_results['service_dependencies']['most_called_services'][:5]:
            dashboard_html += f"<li>{service}: {calls} calls</li>"

        dashboard_html += """
                </ul>
            </div>

            <div class="metric">
                <h3 > Performance Metrics</h3>
                <p > Services by Response Time:</p>
                <ul>
        """

        performance = analysis_results['performance_metrics']['service_performance']
        sorted_perf = sorted(performance.items(), key = lambda x: x[1]['mean_duration'],
            reverse = True)

        for service, metrics in sorted_perf[:5]:
            dashboard_html += f"<li>{service}: {metrics['mean_duration']:.2f}ms avg</li>"

        dashboard_html += """
                </ul>
            </div>

            <div class="metric">
                <h3 > Visualizations</h3>
                <ul>
                    <li><a href="dependency_graph_interactive.html">Interactive Dependency Graph</a></li>
                    <li><a href="performance_dashboard.html">Performance Dashboard</a></li>
                    <li><a href="flow_patterns.html">Flow Patterns</a></li>
                    <li><a href="error_analysis.html">Error Analysis</a></li>
                </ul>
            </div>
        </body>
        </html>
        """

        # Save dashboard
        with open(output_dir / 'dashboard.html', 'w') as f:
            f.write(dashboard_html)


async def main():
    """Main entry point for Jaeger flow analysis."""
    parser = argparse.ArgumentParser(
        description='Analyze Jaeger traces for service flow visualization'
    )
    parser.add_argument(
        '--jaeger-url',
        default='http://localhost:16686',
        help='Jaeger UI URL'
    )
    parser.add_argument(
        '--time-range',
        default='1h',
        help='Time range to analyze (e.g., 1h, 30m, 2d)'
    )
    parser.add_argument(
        '--operation',
        help='Filter by operation name'
    )
    parser.add_argument(
        '--output',
        default='docs/jaeger-analysis',
        help='Output directory for analysis results'
    )

    args = parser.parse_args()

    analyzer = JaegerFlowAnalyzer(
        jaeger_url = args.jaeger_url,
        output_dir = args.output
    )

    try:
        results = await analyzer.analyze_traces(
            time_range = args.time_range,
            operation_filter = args.operation
        )

        if results:
            logger.info("Analysis completed successfully")
            print("\nAnalysis Summary:")
            print(f"  Traces analyzed: {results['metadata']['trace_count']}")
            print(f"  Time range: {results['metadata']['time_range']}")
            print(f"  Output directory: {args.output}")
            print(f"  Dashboard: {args.output}/visualizations/dashboard.html")
        else:
            logger.warning("No traces found for analysis")

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
