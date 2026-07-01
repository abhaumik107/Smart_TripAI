from typing import List

import folium
import streamlit as st
from streamlit_folium import st_folium

import config
from algorithms.route_builder import RouteStop
from api.places import PlacesClient, GeocodingError
from services.optimizer import (
    DayItineraryResult,
    ItineraryResult,
    MultiDayItineraryResult,
    TripOptimizer,
)
from utils.helpers import format_minutes_as_hours_text, get_logger

logger = get_logger(__name__)

st.set_page_config(
    page_title="SmartTrip AI",
    page_icon="compass",
    layout="wide",
    initial_sidebar_state="expanded",
)


THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700;800&family=Sora:wght@400;500;600;700;800&display=swap');

:root {
    --amber: #FFB020; --teal: #22D3C5;
    --bg-void: #0F1115; --bg-panel: #15171D; --bg-card: #1C1F27;
    --border-glow: #2E3340; --text-bright: #F6F7FA; --text-dim: #A4ABBC;
}

* { font-family: 'Sora', sans-serif; font-size: 1.18rem; }
h1, h2, h3, .hero-title { font-family: 'Space Grotesk', sans-serif !important; }

.stApp {
    background:
        radial-gradient(ellipse 900px 600px at 12% 0%, rgba(34,211,197,.10) 0%, transparent 55%),
        radial-gradient(ellipse 800px 700px at 92% 15%, rgba(255,176,32,.08) 0%, transparent 55%),
        var(--bg-void);
    background-attachment: fixed;
}

.blob {
    position: fixed; border-radius: 50%; pointer-events: none; z-index: 0;
    filter: blur(80px); opacity: .25; animation: blobfloat 22s ease-in-out infinite;
}
@keyframes blobfloat {
    0%, 100% { transform: translateY(0) translateX(0) scale(1); }
    50% { transform: translateY(-18px) translateX(14px) scale(1.05); }
}

/* Lock sidebar open: hide the collapse arrow + collapsed-state trigger */
[data-testid="stSidebarCollapsedControl"] { display: none !important; }
button[kind="header"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }

.hero-title {
    font-size: 4.1rem; font-weight: 800;
    background: linear-gradient(90deg, var(--teal) 0%, var(--amber) 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; letter-spacing: -.03em; line-height: 1.05;
    background-size: 200% auto; animation: titleshine 9s linear infinite;
    display: inline-block;
    filter: drop-shadow(0 0 20px rgba(34,211,197,.2));
}
@keyframes titleshine {
    0% { background-position: 0% center; }
    100% { background-position: 200% center; }
}
.hero-icon {
    display: inline-block; animation: pulse-glow 3.2s ease-in-out infinite; font-size: 3rem;
}
@keyframes pulse-glow {
    0%, 100% { transform: scale(1); filter: drop-shadow(0 0 6px rgba(255,176,32,.4)); }
    50% { transform: scale(1.06); filter: drop-shadow(0 0 14px rgba(255,176,32,.7)); }
}
.hero-sub {
    color: var(--text-dim); font-size: 1.3rem; font-weight: 500; margin-top: .5rem;
}

[data-testid="stSidebar"] { background: var(--bg-panel) !important; border-right: 1px solid var(--border-glow) !important; }
[data-testid="stSidebar"] .stTextInput input, [data-testid="stSidebar"] .stNumberInput input {
    border-radius: 12px !important; border: 1.5px solid var(--border-glow) !important;
    background: var(--bg-card) !important; color: var(--text-bright) !important;
    font-weight: 600 !important; font-size: 1.15rem !important;
    transition: border-color .2s ease, box-shadow .2s ease !important;
}
[data-testid="stSidebar"] .stTextInput input:focus, [data-testid="stSidebar"] .stNumberInput input:focus {
    border-color: var(--teal) !important; box-shadow: 0 0 0 3px rgba(34,211,197,.15) !important;
}
[data-testid="stSidebar"] label { font-weight: 700 !important; color: var(--text-bright) !important; font-size: 1.15rem !important; }
[data-testid="stSidebar"] .stCaption, [data-testid="stSidebar"] small { color: var(--text-dim) !important; font-size: 1rem !important; }

[data-testid="stSidebar"] [data-baseweb="tag"] {
    background: var(--teal) !important; color: #06231F !important;
    border-radius: 999px !important; font-weight: 700 !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: var(--bg-card) !important; border-color: var(--border-glow) !important; border-radius: 12px !important;
}

[data-testid="stSidebar"] [data-baseweb="slider"] [role="slider"] {
    background: var(--amber) !important; box-shadow: 0 0 0 5px rgba(255,176,32,.18) !important;
}
[data-testid="stSidebar"] [data-baseweb="slider"] > div > div { background: linear-gradient(90deg, var(--teal), var(--amber)) !important; }

.stButton button[kind="primary"] {
    background: linear-gradient(135deg, var(--teal), var(--amber)) !important;
    border: none !important; border-radius: 14px !important;
    font-weight: 800 !important; font-size: 1.25rem !important;
    padding: .9rem 1rem !important; color: #0F1115 !important;
    box-shadow: 0 6px 20px rgba(34,211,197,.25) !important;
    transition: transform .15s ease, box-shadow .15s ease !important;
}
.stButton button[kind="primary"] * { color: #0F1115 !important; }
.stButton button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 10px 28px rgba(255,176,32,.3) !important;
}
.stButton button[kind="primary"]:active { transform: translateY(1px) !important; }

[data-testid="stTickBarMin"], [data-testid="stTickBarMax"],
[data-testid="stSidebar"] [data-baseweb="slider"] > div:last-child span {
    color: #0F1115 !important; font-weight: 700 !important;
}

[data-testid="stMetric"] {
    background: var(--bg-card); border-radius: 16px; padding: 1.2rem 1.4rem;
    border: 1px solid var(--border-glow); box-shadow: 0 4px 20px rgba(0,0,0,.35);
    transition: transform .2s ease, border-color .2s ease;
}
[data-testid="stMetric"]:hover { transform: translateY(-3px); border-color: var(--teal); }
[data-testid="stMetricValue"] {
    font-family: 'Space Grotesk', sans-serif !important; font-weight: 700 !important;
    font-size: 1.8rem !important; color: var(--teal) !important;
}
[data-testid="stMetricLabel"] { font-weight: 700 !important; font-size: 1.1rem !important; color: var(--text-dim) !important; }

.stTabs [data-baseweb="tab-list"] {
    background: var(--bg-card); border-radius: 14px; padding: 5px; gap: 5px; border: 1px solid var(--border-glow);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 10px; font-weight: 700; font-size: 1.1rem;
    color: var(--text-dim); padding: .6rem 1.4rem; transition: all .2s ease;
}
.stTabs [aria-selected="true"] { background: linear-gradient(135deg, var(--teal), var(--amber)) !important; color: #0F1115 !important; }

/* Itinerary: responsive 3-column grid that fits within Streamlit's content area */
.stop-grid-3 {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: .75rem;
    width: 100%;
    box-sizing: border-box;
    overflow: hidden;
}
@media (max-width: 1100px) { .stop-grid-3 { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 700px)  { .stop-grid-3 { grid-template-columns: minmax(0, 1fr); } }

.stop-card {
    background: #232733; border-radius: 14px; padding: .85rem 1rem;
    border: 1px solid var(--border-glow); border-left: 4px solid var(--teal);
    box-shadow: 0 4px 18px rgba(0,0,0,.3);
    transition: transform .2s ease, box-shadow .2s ease;
    animation: cardrise .4s ease backwards;
    display: flex; flex-direction: row; gap: .75rem; align-items: flex-start;
    min-width: 0; overflow: hidden; box-sizing: border-box;
}
.stop-card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,.45); }
@keyframes cardrise {
    from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); }
}
.stop-badge {
    display: inline-flex; align-items: center; justify-content: center;
    width: 42px; height: 42px; border-radius: 12px;
    color: #0F1115; font-weight: 800; font-family: 'Space Grotesk', sans-serif;
    font-size: 1.2rem; flex-shrink: 0;
}
.stop-name { font-weight: 800; font-size: 1.1rem; color: var(--text-bright); word-wrap: break-word; overflow-wrap: break-word; }
.stop-address { color: var(--text-dim); font-size: .88rem; margin-top: 2px; word-wrap: break-word; overflow-wrap: break-word; }
.stop-travel { color: var(--teal); font-size: .92rem; font-weight: 700; margin-bottom: .4rem; }

.score-pill { display: inline-block; background: var(--amber); color: #2B1A00; font-weight: 800; font-size: 1rem; padding: .3rem .8rem; border-radius: 999px; }

.why-selected {
    margin-top: .65rem; padding-top: .55rem; border-top: 1px solid var(--border-glow);
}
.why-selected-label { color: var(--text-dim); font-size: .82rem; font-weight: 700; letter-spacing: .02em; text-transform: uppercase; margin-bottom: .3rem; }
.why-selected-reason {
    display: inline-block; background: rgba(255,255,255,.04); border: 1px solid var(--border-glow);
    color: var(--text-dim); font-size: .85rem; font-weight: 600;
    padding: .2rem .6rem; border-radius: 8px; margin: 0 .35rem .35rem 0;
}

.day-banner {
    background: var(--bg-card); border: 1px solid var(--border-glow); border-left: 3px solid var(--amber);
    border-radius: 16px; padding: 1.1rem 1.5rem; margin-bottom: 1.1rem;
    font-weight: 700; font-size: 1.2rem; color: var(--text-bright);
}

.stAlert { border-radius: 14px !important; font-size: 1.15rem !important; }
div[data-testid="stNotificationContentInfo"], div[data-testid="stNotificationContentWarning"], div[data-testid="stNotificationContentError"] { color: var(--text-bright) !important; }

.stMarkdown, p, span, label, .stCaption { color: var(--text-bright); }
.hero-sub, .stop-address, [data-testid="stMetricLabel"] { color: var(--text-dim) !important; }
h3 { font-size: 1.6rem !important; }
::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-thumb { background: var(--teal); border-radius: 8px; }
iframe { border-radius: 16px !important; border: 1px solid var(--border-glow) !important; }

/* hide the "Press Enter to apply" tooltip on text inputs */
[data-testid="InputInstructions"] { display: none !important; }
small[class*="instructions"] { display: none !important; }
</style>
"""


def inject_decor():
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    st.markdown(
        """
        <div class="blob" style="width:420px;height:420px;background:#22D3C5;top:-100px;right:-100px;animation-delay:0s"></div>
        <div class="blob" style="width:340px;height:340px;background:#FFB020;bottom:8%;left:-110px;animation-delay:5s"></div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar():
    st.sidebar.markdown(
        '<div style="font-family:\'Space Grotesk\',sans-serif;font-size:1.9rem;font-weight:800;'
        'background:linear-gradient(90deg,#22D3C5,#FFB020);-webkit-background-clip:text;'
        '-webkit-text-fill-color:transparent;background-clip:text;">'
        'SmartTrip AI</div>',
        unsafe_allow_html=True,
    )
    st.sidebar.caption("Plan an optimized, time-aware travel itinerary.")

    city = st.sidebar.text_input("City", placeholder="e.g. Mumbai", key="sb_city")
    starting_location = st.sidebar.text_input(
        "Starting Location", placeholder="e.g. Gateway of India", key="sb_start"
    )

    num_days = st.sidebar.number_input(
        "Number of Days", min_value=1, max_value=7, value=1, step=1,
        help="Each day starts fresh from your starting location.", key="sb_days"
    )

    available_hours = st.sidebar.slider(
        "Available Time per Day (hours)", min_value=1.0, max_value=12.0, value=5.0, step=0.5,
        key="sb_hours"
    )
    interests = st.sidebar.multiselect(
        "Interests", options=config.ALL_INTERESTS, default=["History", "Food"], key="sb_interests"
    )

    if config.MOCK_MODE:
        st.sidebar.info(
            "Running in MOCK_MODE (no GOOGLE_PLACES_API_KEY set). "
            "Synthetic attraction data is being used."
        )

    submitted = st.sidebar.button(
        "Generate Itinerary", type="primary", use_container_width=True
    )
    return city, starting_location, available_hours, int(num_days), interests, submitted


def _normalized_trip_score(total_score: float, stop_count: int) -> int:
    """Display-only normalization of the raw score onto a 0-100 scale.
    Does not alter the underlying scoring/optimization logic in any way."""
    if stop_count <= 0:
        return 0
    avg_score_per_stop = total_score / stop_count
    return max(0, min(100, round(avg_score_per_stop * 100)))


def render_summary(total_score, total_visit_minutes, total_travel_minutes, utilization_percent, stop_count: int):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Trip Score", f"{_normalized_trip_score(total_score, stop_count)}/100")
    col2.metric("Visit Time", format_minutes_as_hours_text(total_visit_minutes))
    col3.metric("Travel Time", format_minutes_as_hours_text(total_travel_minutes))
    col4.metric("Time Utilization", f"{utilization_percent:.1f}%")


def render_map(start_coords, stops: List[RouteStop], map_key: str):
    fmap = folium.Map(location=start_coords, zoom_start=13, tiles="cartodbdark_matter")

    folium.Marker(
        location=start_coords,
        tooltip="Start",
        icon=folium.Icon(color="green", icon="play", prefix="fa"),
    ).add_to(fmap)

    route_points = [start_coords]
    for stop in stops:
        coords = (stop.attraction.latitude, stop.attraction.longitude)
        route_points.append(coords)
        folium.Marker(
            location=coords,
            tooltip=f"{stop.arrival_order}. {stop.attraction.name}",
            popup=(
                f"<b>{stop.attraction.name}</b><br>"
                f"Score: {stop.attraction.personalized_score:.2f}<br>"
                f"Visit: {format_minutes_as_hours_text(stop.attraction.visit_duration_minutes)}"
            ),
            icon=folium.Icon(color="blue", icon="info-sign"),
        ).add_to(fmap)

    if len(route_points) > 1:
        folium.PolyLine(route_points, color="#22D3C5", weight=4, opacity=0.85).add_to(fmap)

    st_folium(fmap, width=None, height=480, key=map_key)


def _why_selected_reasons(stop: RouteStop, user_interests) -> List[str]:
    """Pure display heuristic for explaining a recommendation.
    Does not read from or alter the recommendation engine / optimizer."""
    score = stop.attraction.personalized_score
    reasons: List[str] = []

    category = getattr(stop.attraction, "category", None) or getattr(stop.attraction, "categories", None)
    if category and user_interests:
        category_text = " ".join(category) if isinstance(category, (list, tuple, set)) else str(category)
        if any(interest.lower() in category_text.lower() for interest in user_interests):
            reasons.append("Matches your interests")

    rating = getattr(stop.attraction, "rating", None)
    if (rating and rating >= 4.3) or score >= 0.85:
        reasons.append("Highly rated")

    review_count = getattr(stop.attraction, "review_count", None) or getattr(stop.attraction, "popularity", None)
    if review_count and review_count >= 500:
        reasons.append("Popular attraction")

    if stop.attraction.visit_duration_minutes <= 45:
        reasons.append("Fits within your available time")

    if 0.7 <= score < 0.85:
        reasons.append("Good overall recommendation score")

    deduped: List[str] = []
    for reason in reasons:
        if reason not in deduped:
            deduped.append(reason)

    if len(deduped) < 2:
        deduped.append("Good overall recommendation score")
    if len(deduped) < 2:
        deduped.append("Fits within your available time")

    return deduped[:3]


def _why_selected_html(reasons: List[str]) -> str:
    pills = "".join(f'<span class="why-selected-reason">{reason}</span>' for reason in reasons)
    return (
        '<div class="why-selected">'
        '<div class="why-selected-label">Why Selected</div>'
        f'<div>{pills}</div>'
        '</div>'
    )


def _stop_card_html(stop: RouteStop, arrival_label: str, travel_text: str, delay: float, accent: str, user_interests) -> str:
    visit_text = format_minutes_as_hours_text(stop.attraction.visit_duration_minutes)
    why_html = _why_selected_html(_why_selected_reasons(stop, user_interests))
    return (
        f'<div class="stop-card" style="animation-delay:{delay}s;border-left-color:{accent}">'
        f'<div class="stop-badge" style="background:{accent};flex-shrink:0">{stop.arrival_order}</div>'
        f'<div style="flex:1;min-width:0">'
        f'<div class="stop-travel" style="color:{accent}">~{arrival_label}{travel_text}</div>'
        f'<div class="stop-name">{stop.attraction.name}</div>'
        f'<div class="stop-address">{stop.attraction.address}</div>'
        f'<div style="margin-top:.4rem;display:flex;flex-wrap:wrap;gap:.4rem;align-items:center">'
        f'<span class="score-pill">score {stop.attraction.personalized_score:.2f}</span>'
        f'<span style="color:#A4ABBC;font-size:.88rem;font-weight:600">{visit_text}</span>'
        f'</div>'
        f'{why_html}'
        f'</div>'
        f'</div>'
    )


def _compute_arrivals(stops: List[RouteStop]):
    cumulative_minutes = 0
    arrivals = []
    for stop in stops:
        cumulative_minutes += stop.travel_minutes_from_previous
        arrival_label = format_minutes_as_hours_text(cumulative_minutes)
        cumulative_minutes += stop.attraction.visit_duration_minutes
        travel_text = (
            f" (+{round(stop.travel_minutes_from_previous)}m travel)"
            if stop.travel_minutes_from_previous else ""
        )
        arrivals.append((arrival_label, travel_text))
    return arrivals


def render_stop_grid(stops: List[RouteStop], arrivals, start_index: int, user_interests):
    cards = []
    for offset, (stop, (arrival_label, travel_text)) in enumerate(zip(stops, arrivals)):
        i = start_index + offset
        accent = "var(--teal)" if i % 2 == 0 else "var(--amber)"
        cards.append(_stop_card_html(stop, arrival_label, travel_text, i * 0.05, accent, user_interests))
    st.markdown('<div class="stop-grid-3">' + "".join(cards) + '</div>', unsafe_allow_html=True)


def render_itinerary(start_coords, stops: List[RouteStop], map_key: str, user_interests=()):
    """Map full-width on top; all stops in a 3-column grid below."""
    st.markdown("### Itinerary Timeline")
    arrivals = _compute_arrivals(stops)

    render_map(start_coords, stops, map_key=map_key)

    if not stops:
        st.warning("No attractions fit within the available time. Try increasing available hours or broadening interests.")
        return

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)
    render_stop_grid(stops, arrivals, start_index=0, user_interests=user_interests)


def render_single_day_result(start_coords, result: ItineraryResult, user_interests=()):
    render_summary(result.total_score, result.total_visit_minutes,
                    result.total_travel_minutes, result.utilization_percent, len(result.stops))
    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
    render_itinerary(start_coords, result.stops, map_key="itinerary_map", user_interests=user_interests)


def render_multi_day_result(start_coords, result: MultiDayItineraryResult, user_interests=()):
    st.markdown("### Trip Overview")
    total_stop_count = sum(len(d.stops) for d in result.days)
    render_summary(result.total_score, result.total_visit_minutes,
                    result.total_travel_minutes, _trip_utilization(result), total_stop_count)
    st.markdown("<div style='height:.9rem'></div>", unsafe_allow_html=True)

    day_labels = [f"Day {d.day_index + 1}" for d in result.days]
    tabs = st.tabs(day_labels)

    for tab, day in zip(tabs, result.days):
        with tab:
            day_score_100 = _normalized_trip_score(day.total_score, len(day.stops))
            st.markdown(
                f'<div class="day-banner">'
                f'Score {day_score_100}/100 · '
                f'{format_minutes_as_hours_text(day.total_visit_minutes)} visiting · '
                f'{format_minutes_as_hours_text(day.total_travel_minutes)} travel · '
                f'{day.utilization_percent:.1f}% time used'
                f'</div>',
                unsafe_allow_html=True,
            )

            if not day.stops:
                st.warning(
                    f"No attractions fit into Day {day.day_index + 1}. "
                    "Try increasing available hours, adding more days, or broadening interests."
                )
                continue

            render_itinerary(start_coords, day.stops, map_key=f"itinerary_map_day_{day.day_index}", user_interests=user_interests)


def _trip_utilization(result: MultiDayItineraryResult) -> float:
    total_available = sum(d.available_minutes for d in result.days)
    total_used = result.total_visit_minutes + result.total_travel_minutes
    return round((total_used / total_available) * 100, 1) if total_available > 0 else 0.0


def main():
    inject_decor()

    st.markdown(
        '<span class="hero-icon"></span> <span class="hero-title">SmartTrip AI</span>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="hero-sub">AI-powered personalized travel itineraries optimized for '
        'your interests and available time.</div>',
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

    city, starting_location, available_hours, num_days, interests, submitted = render_sidebar()

    if submitted:
        if not city or not starting_location:
            st.error("Please provide both a city and a starting location.")
            st.session_state.pop("trip_result", None)
            return

        if not interests:
            st.error("Please select at least one interest.")
            st.session_state.pop("trip_result", None)
            return

        client = PlacesClient()

        with st.status("Generating your itinerary...", expanded=True) as status:
            status.update(label="Finding nearby attractions...")
            try:
                start_coords = client.geocode(starting_location, city=city)
            except GeocodingError as exc:
                status.update(label="Could not resolve starting location", state="error")
                st.error(str(exc))
                st.session_state.pop("trip_result", None)
                return

            categories = sorted({
                cat for interest in interests for cat in config.INTEREST_CATEGORY_MAP[interest]
            })
            attractions = client.fetch_nearby_attractions(start_coords, categories)

            if not attractions:
                status.update(label="No attractions found", state="error")
                st.warning("No attractions found for the selected city and interests.")
                st.session_state.pop("trip_result", None)
                return

            status.update(label="Generating personalized scores...")
            optimizer = TripOptimizer()

            status.update(label="Optimizing itinerary...")
            if num_days == 1:
                result = optimizer.generate_itinerary(
                    start_location=start_coords,
                    candidate_attractions=attractions,
                    user_interests=set(interests),
                    available_hours=available_hours,
                )
            else:
                result = optimizer.generate_multi_day_itinerary(
                    start_location=start_coords,
                    candidate_attractions=attractions,
                    user_interests=set(interests),
                    available_hours_per_day=available_hours,
                    num_days=num_days,
                )

            status.update(label="Building interactive map...")
            status.update(label="Itinerary ready!", state="complete", expanded=False)

        # save result to session_state so it does not disappear when the
        # map widget triggers a rerun (submitted is only True for one run)
        st.session_state["trip_result"] = {
            "num_days": num_days,
            "start_coords": start_coords,
            "result": result,
            "interests": interests,
        }

    stored = st.session_state.get("trip_result")
    if not stored:
        st.info("Fill in the sidebar and click Generate Itinerary to get started.")
        return

    st.divider()
    if stored["num_days"] == 1:
        render_single_day_result(stored["start_coords"], stored["result"], stored.get("interests", ()))
    else:
        render_multi_day_result(stored["start_coords"], stored["result"], stored.get("interests", ()))


if __name__ == "__main__":
    main()
