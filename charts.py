"""Build calm-themed Plotly charts from an animal's environmental logs."""
import plotly.graph_objects as go
from plotly.io import to_html

# calm palette matching the WildNest theme
SAGE = '#6b9080'
SAGE_DARK = '#52796f'
TERRACOTTA = '#cb997e'
BLUE = '#6a8caf'
AMBER = '#d9a441'
ROSE = '#c47b6e'
TEXT = '#33413a'
GRID = '#efece4'


def _base_layout(title, height=280):
    return dict(
        title=dict(text=title, font=dict(size=14, color=TEXT, family='Nunito Sans')),
        height=height,
        margin=dict(l=45, r=20, t=40, b=35),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color=TEXT, family='Nunito Sans', size=11),
        xaxis=dict(gridcolor=GRID, zeroline=False),
        yaxis=dict(gridcolor=GRID, zeroline=False),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
                    font=dict(size=10)),
        hovermode='x unified',
    )


def _div(fig):
    return to_html(fig, full_html=False, include_plotlyjs=False,
                   config={'displayModeBar': False, 'responsive': True})


def build_env_charts(logs):
    """Return a dict of chart-name -> HTML div. Only includes charts with data."""
    if not logs:
        return {}

    dates = [log.timestamp for log in logs]
    charts = {}

    def series(attr):
        return [getattr(log, attr) for log in logs]

    def has_data(attr):
        return any(getattr(log, attr) is not None for log in logs)

    # 1. Temperature & Humidity (dual axis)
    if has_data('temperature_f') or has_data('humidity_pct'):
        fig = go.Figure()
        if has_data('temperature_f'):
            fig.add_trace(go.Scatter(
                x=dates, y=series('temperature_f'), name='Temp (°F)',
                mode='lines+markers', line=dict(color=TERRACOTTA, width=2.5),
                marker=dict(size=6)))
        if has_data('humidity_pct'):
            fig.add_trace(go.Scatter(
                x=dates, y=series('humidity_pct'), name='Humidity (%)',
                mode='lines+markers', line=dict(color=BLUE, width=2.5),
                marker=dict(size=6), yaxis='y2'))
        layout = _base_layout('Temperature & Humidity')
        layout['yaxis2'] = dict(overlaying='y', side='right', gridcolor=GRID,
                                zeroline=False, title='Humidity %')
        layout['yaxis']['title'] = 'Temp °F'
        fig.update_layout(**layout)
        charts['temp_humidity'] = _div(fig)

    # 2. Weight trend
    if has_data('weight_g'):
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates, y=series('weight_g'), name='Weight (g)',
            mode='lines+markers', line=dict(color=SAGE_DARK, width=2.5),
            marker=dict(size=6), fill='tozeroy',
            fillcolor='rgba(107,144,128,0.10)'))
        fig.update_layout(**_base_layout('Weight Trend'))
        charts['weight'] = _div(fig)

    # 3. Feeding amount (bars)
    if has_data('feeding_amount_g'):
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=dates, y=series('feeding_amount_g'), name='Feeding (g)',
            marker_color=SAGE))
        fig.update_layout(**_base_layout('Feeding Amount'))
        charts['feeding'] = _div(fig)

    # 4. Stress & Activity (1-5)
    if has_data('stress_level') or has_data('activity_level'):
        fig = go.Figure()
        if has_data('stress_level'):
            fig.add_trace(go.Scatter(
                x=dates, y=series('stress_level'), name='Stress',
                mode='lines+markers', line=dict(color=ROSE, width=2.5),
                marker=dict(size=6)))
        if has_data('activity_level'):
            fig.add_trace(go.Scatter(
                x=dates, y=series('activity_level'), name='Activity',
                mode='lines+markers', line=dict(color=SAGE, width=2.5),
                marker=dict(size=6)))
        layout = _base_layout('Stress & Activity (1–5)')
        layout['yaxis']['range'] = [0, 5.5]
        fig.update_layout(**layout)
        charts['stress_activity'] = _div(fig)

    return charts
