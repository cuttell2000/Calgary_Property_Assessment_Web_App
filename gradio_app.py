import html

import folium
import gradio as gr
import spaces

from app import app as flask_app
from app import calgary_center, communities_gdf, sector_gdf


@spaces.GPU
def show_community_map(community_name):
    if not community_name:
        return "Select a community to load its property map.", ""

    with flask_app.test_client() as client:
        response = client.post("/map", data={"community_name": community_name})
        result = response.get_json()

    if response.status_code >= 400:
        error = html.escape(result.get("error", "Unable to load the property map."))
        return "Map unavailable", f"<p role='alert'>{error}</p>"

    title = html.escape(result["community_name"])
    return f"### {title} | Property Assessment Map", result["map_html"]


def show_calgary_overview():
    if communities_gdf is None or sector_gdf is None:
        return (
            "Map unavailable",
            "<p role='alert'>Community and sector data did not load. Please try again later.</p>",
        )

    calgary_map = folium.Map(location=calgary_center, zoom_start=10)
    folium.GeoJson(
        communities_gdf.to_json(),
        name="Community Boundaries",
        tooltip=folium.features.GeoJsonTooltip(fields=["name"]),
    ).add_to(calgary_map)
    folium.GeoJson(
        sector_gdf.to_json(),
        name="Community Sectors",
        style_function=lambda _feature: {
            "fillColor": "none",
            "color": "red",
            "weight": 2,
        },
        tooltip=folium.features.GeoJsonTooltip(fields=["sector"]),
    ).add_to(calgary_map)
    folium.LayerControl().add_to(calgary_map)

    return "### Calgary Overview", calgary_map._repr_html_()


community_names = (
    sorted(communities_gdf["name"].dropna().unique().tolist())
    if communities_gdf is not None
    else []
)

with gr.Blocks(title="Calgary Property Assessment Map") as demo:
    gr.Markdown("# Calgary Property Assessment Map")
    gr.Markdown(
        "Explore property assessment boundaries by community using City of Calgary open data."
    )

    with gr.Row():
        community_dropdown = gr.Dropdown(
            choices=community_names,
            label="Choose a community",
            scale=4,
        )
        show_map_button = gr.Button("Show Property Map", variant="primary")
        overview_button = gr.Button("View Calgary Overview")

    map_title = gr.Markdown()
    map_output = gr.HTML(
        value="<p>Select a community or view the Calgary overview to display a map.</p>",
        elem_id="property-map",
    )

    show_map_button.click(
        fn=show_community_map,
        inputs=community_dropdown,
        outputs=[map_title, map_output],
    )
    overview_button.click(
        fn=show_calgary_overview,
        outputs=[map_title, map_output],
    )


if __name__ == "__main__":
    demo.launch()
