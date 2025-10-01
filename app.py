import os
from flask import Flask, render_template, request
import geopandas as gpd
import folium
import json
import pandas as pd

app = Flask(__name__)

# --- Helper Function (Remains the same) ---
def format_assessed_value(row):
    """
    Formats the various assessed value columns into a single HTML string for Folium popup.
    """
    assessed = row.get('assessed_value')
    re_assessed = row.get('re_assessed_value')
    nr_assessed = row.get('nr_assessed_value')
    fl_assessed = row.get('fl_assessed_value')

    formatted_values = []
    
    if pd.notna(assessed):
        formatted_values.append(f"Assessed Value: ${assessed:,.0f}")
    if pd.notna(re_assessed):
        formatted_values.append(f"Residential Assessed Value: ${re_assessed:,.0f}")
    if pd.notna(nr_assessed):
        formatted_values.append(f"Non-Residential Assessed Value: ${nr_assessed:,.0f}")
    if pd.notna(fl_assessed):
        formatted_values.append(f"Farm Land Assessed Value: ${fl_assessed:,.0f}")

    return "<br>".join(formatted_values) if formatted_values else "No assessed value information"

# --- Global Data Loading ---
try:
    properties_gdf = gpd.read_file("https://data.calgary.ca/resource/4bsw-nn7w.geojson?$limit=700000")
    communities_gdf = gpd.read_file('https://data.calgary.ca/resource/surr-xmvs.geojson')
    sector_gdf = gpd.read_file('https://data.calgary.ca/resource/mz2j-7eb5.geojson')

    # 1. Pre-process properties
    for col in ['assessed_value', 're_assessed_value', 'nr_assessed_value', 'fl_assessed_value']:
        if col in properties_gdf.columns:
            properties_gdf[col] = pd.to_numeric(properties_gdf[col], errors='coerce')
    properties_gdf['formatted_assessed_values'] = properties_gdf.apply(format_assessed_value, axis=1)
    if 'mod_date' in properties_gdf.columns:
        properties_gdf['mod_date'] = properties_gdf['mod_date'].astype(str)
        
    # 2. Pre-process communities
    if 'created_dt' in communities_gdf.columns:
        communities_gdf['created_dt'] = communities_gdf['created_dt'].astype(str)
    if 'modified_dt' in communities_gdf.columns:
        communities_gdf['modified_dt'] = communities_gdf['modified_dt'].astype(str)
        
    # 3. Pre-process sectors
    if sector_gdf.crs and sector_gdf.crs.to_string() != 'EPSG:4326':
        sector_gdf = sector_gdf.to_crs(epsg=4326)

    # Calculate Calgary center for the overview map (e.g., using all community centroids)
    calgary_center = [communities_gdf.geometry.centroid.y.mean(), communities_gdf.geometry.centroid.x.mean()]

except Exception as e:
    print(f"Error loading GeoJSON data: {e}")
    properties_gdf = None
    communities_gdf = None
    sector_gdf = None
    calgary_center = [51.0447, -114.0719] # Default to city center


## --- New Route for Calgary Overview Map ---

@app.route('/calgary_overview')
def calgary_overview():
    if communities_gdf is None or sector_gdf is None:
        return "Error: Data not loaded.", 500

    # Create map centered on Calgary
    calgary_map = folium.Map(location=calgary_center, zoom_start=10) # Zoom out for city view

    # Add ALL community boundaries as a layer
    folium.GeoJson(
        communities_gdf.to_json(),
        name='Community Boundaries',
        tooltip=folium.features.GeoJsonTooltip(fields=['name']),
        # style_function=lambda x: {'color': 'gray', 'weight': 1, 'fillOpacity': 0.05}
    ).add_to(calgary_map)

    # Add ALL sectors as a layer
    folium.GeoJson(
        sector_gdf.to_json(),
        name='Community Sectors',
        style_function=lambda x: {'fillColor': 'none', 'color': 'red', 'weight': 2},
        tooltip=folium.features.GeoJsonTooltip(fields=['sector']) 
    ).add_to(calgary_map)

    # Add Layer Control
    folium.LayerControl().add_to(calgary_map)

    map_html = calgary_map._repr_html_()

    # Pass a name and a link back to the selection page
    return render_template('map.html', map_html=map_html, community_name="Calgary Overview")


## --- Existing Routes (Minor changes to index page link) ---

@app.route('/')
def index():
    community_names = []
    if communities_gdf is not None:
        community_names = sorted(communities_gdf['name'].unique().tolist())
    
    # Pass the overview link to the index template
    return render_template('index.html', community_names=community_names)


@app.route('/map', methods=['POST'])
def show_map():
    selected_community = request.form.get('community_name')

    if not selected_community or properties_gdf is None or communities_gdf is None or sector_gdf is None:
        return "Error: Community not selected or data not loaded.", 400
    
    # Step 1: Filter the Boundary GDF using the user's selection (communities_gdf['NAME'])
    # This works because the user's selection comes from this column, whether it's 
    # 'ALYTH/BONNYBROOK' or '01B'.
    community_boundary = communities_gdf[communities_gdf['name'] == selected_community].copy()

    if community_boundary.empty:
        # Should not happen if the dropdown is populated from communities_gdf['NAME']
        return f"No boundary data found for community: {selected_community}", 404
    
    # Step 2: Extract the GUARANTEED common key (COMM_CODE)
    # This is the single, universal key needed to filter the properties.
    # It will be 'AYB' for named communities or '01B' for coded communities.
    property_filter_code = community_boundary['comm_code'].iloc[0]

    # Step 3: Filter the Properties GDF using the extracted COMM_CODE
    community_properties_gdf = properties_gdf[
        properties_gdf['comm_code'] == property_filter_code
    ].copy()

    # ----------------------------------------------------------------------
    # Remainder of the Logic (Error Check and Map Generation)
    
    if community_properties_gdf.empty:
        # Get the full property name for a clean error message
        long_comm_name = community_boundary.iloc[0]['name'] 
        return f"No property data found for community: {long_comm_name} (Filter Code: {property_filter_code}).", 404
    
    # Step 4: Extract the correct long name for the map title/header
    # Use the COMM_NAME from the properties GDF, which gives the official name 
    # (e.g., 'RESIDUAL WARD 1 - SUB AREA 1B') for coded communities.
    long_comm_name = community_properties_gdf['comm_name'].iloc[0]

     # ... (Rest of your mapping code: CRS, centering, map generation) ...
    
    # Example map setup (ensure your CRS conversions and Folium code are here)
    community_properties_gdf = community_properties_gdf.to_crs(epsg=4326)
    community_boundary = community_boundary.to_crs(epsg=4326)


    # Calculate map center and create the base Folium map
    map_center = [community_boundary.geometry.centroid.y.iloc[0],
                  community_boundary.geometry.centroid.x.iloc[0]]
    community_map = folium.Map(location=map_center, zoom_start=14)

    # Add Community Boundary to the map
    folium.GeoJson(
        community_boundary,
        name=f"Boundary: {long_comm_name}",
        style_function=lambda x: {'fillColor': '#007bff', 'color': 'black', 'weight': 2, 'fillOpacity': 0.1}
    ).add_to(community_map)


    # Add the filtered properties to the map
    if community_properties_gdf.crs and community_properties_gdf.crs.to_string() != 'EPSG:4326':
        community_properties_gdf = community_properties_gdf.to_crs(epsg=4326)

    folium.GeoJson(
        community_properties_gdf.to_json(),
        name=f'{selected_community} Properties',
        tooltip=folium.features.GeoJsonTooltip(
            fields=['address', 'assessment_class_description', 'formatted_assessed_values'],
            aliases=['Address', 'Class', 'Assessed Values']
        ),
        popup=folium.features.GeoJsonPopup(
            fields=['address', 'assessment_class_description', 'formatted_assessed_values'],
            aliases=['Address', 'Class', 'Assessed Values'] 
        ),
        style_function=lambda x: {'color': 'blue', 'weight': 1, 'fillColor': 'none'},
        highlight_function=lambda x: {'fillColor': '#ffff00', 'color': '#000000', 'fillOpacity': 0.50, 'weight': 0.1}, # Hover style
        tooltip_anchor='right' # Optional: Adjust tooltip position
    ).add_to(community_map)

    # We only need LayerControl if we have multiple layers, which we do here (Properties, Boundary)
    folium.LayerControl().add_to(community_map) 

    map_html = community_map._repr_html_()

    # Pass the long name and map to the template
    return render_template('map.html', map_html=map_html, community_name=long_comm_name)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)