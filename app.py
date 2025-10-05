import os
from flask import Flask, render_template, request, Response
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

# --- Global Data Loading (Only load small files to save memory) ---
properties_gdf = None # Explicitly set large GDF to None/Unused
communities_gdf = None
sector_gdf = None
calgary_center = [51.0447, -114.0719] # Default center

try:
    # Load ONLY the smaller, necessary boundary files globally
    communities_gdf = gpd.read_file('https://data.calgary.ca/resource/surr-xmvs.geojson')
    sector_gdf = gpd.read_file('https://data.calgary.ca/resource/mz2j-7eb5.geojson')
    
    # 1. Pre-process communities
    if 'created_dt' in communities_gdf.columns:
        communities_gdf['created_dt'] = communities_gdf['created_dt'].astype(str)
    if 'modified_dt' in communities_gdf.columns:
        communities_gdf['modified_dt'] = communities_gdf['modified_dt'].astype(str)
        
    # 2. Pre-process sectors
    if sector_gdf.crs and sector_gdf.crs.to_string() != 'EPSG:4326':
        sector_gdf = sector_gdf.to_crs(epsg=4326)

    # Calculate Calgary center for the overview map
    # Ensure communities_gdf is converted to 4326 before centroid calculation if needed
    if communities_gdf.crs and communities_gdf.crs.to_string() != 'EPSG:4326':
        communities_gdf = communities_gdf.to_crs(epsg=4326)
    
    calgary_center = [communities_gdf.geometry.centroid.y.mean(), communities_gdf.geometry.centroid.x.mean()]

except Exception as e:
    print(f"Error loading initial GeoJSON data: {e}")
    communities_gdf = None
    sector_gdf = None
    # calgary_center remains the default

## --- New Route for Calgary Overview Map ---

@app.route('/calgary_overview')
def calgary_overview():
    # if communities_gdf is None or sector_gdf is None:
    #     return "Error: Data not loaded.", 500
    
    # Assume communities_gdf, sector_gdf, and calgary_center are defined globally or within scope

    if communities_gdf is None or sector_gdf is None:
        return "Error: Data not loaded. Please ensure data is loaded at startup.", 500

    # Create map centered on Calgary
    calgary_map = folium.Map(location=calgary_center, zoom_start=10) # Zoom out for city view

    # Add ALL community boundaries as a layer
    folium.GeoJson(
        communities_gdf.to_json(),
        name='Community Boundaries',
        tooltip=folium.features.GeoJsonTooltip(fields=['name']),
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
    community_name = "Calgary Overview"

    return render_template('map.html', map_html=map_html, community_name=community_name)


## --- Existing Routes ---

@app.route('/')
def index():
    community_names = []
    if communities_gdf is not None:
        # NOTE: Using 'name' (lowercase) based on your code and open data structure
        community_names = sorted(communities_gdf['name'].unique().tolist())
        
    return render_template('index.html', community_names=community_names)


@app.route('/map', methods=['POST'])
def show_map():
    selected_community = request.form.get('community_name')

    # # Note: properties_gdf is intentionally None globally, so we skip that check here.
    # if not selected_community or communities_gdf is None:
    #     return "Error: Community not selected or boundary data not loaded.", 400
    
    if not selected_community or communities_gdf is None:
        # Instead of returning an error page, we return a JSON error for the AJAX handler
        return Response('{"error": "Community not selected or boundary data not loaded."}', 
                        status=400, 
                        mimetype='application/json')
    
    # Step 1: Filter the Boundary GDF using the user's selection
    community_boundary = communities_gdf[communities_gdf['name'] == selected_community].copy()

    # if community_boundary.empty:
    #     return f"No boundary data found for community: {selected_community}", 404
    
    if community_boundary.empty:
        return Response('{"error": "No boundary data found for community."}', 
                        status=404, 
                        mimetype='application/json')
        
    # Step 2: Extract the GUARANTEED common key (comm_code)
    property_filter_code = community_boundary['comm_code'].iloc[0]

    # --- CRITICAL FIX: Load and Filter Properties Data at the Source (Memory Saver) ---
    BASE_PROPERTY_URL = "https://data.calgary.ca/resource/4bsw-nn7w.geojson"
    
    # Construct the SoQL query to filter by comm_code
    # This loads ONLY the data we need for the specific community.
    # filter_query = f"?$where=comm_code='{property_filter_code}'"
    filter_query = f"?$where=comm_code='{property_filter_code}'&$limit=700000"
    full_url = BASE_PROPERTY_URL + filter_query
    

    try:
        community_properties_gdf = gpd.read_file(full_url)
    except Exception as e:
        print(f"Error loading filtered property data from URL: {e}")
        return Response('{"error": "Server error loading properties."}', 
                        status=500, 
                        mimetype='application/json')

    # Step 3: APPLY PRE-PROCESSING to the newly loaded GDF
    # This must be done here since it was removed from global setup.
    for col in ['assessed_value', 're_assessed_value', 'nr_assessed_value', 'fl_assessed_value']:
        if col in community_properties_gdf.columns:
            community_properties_gdf[col] = pd.to_numeric(community_properties_gdf[col], errors='coerce')
    community_properties_gdf['formatted_assessed_values'] = community_properties_gdf.apply(format_assessed_value, axis=1)
    if 'mod_date' in community_properties_gdf.columns:
        community_properties_gdf['mod_date'] = community_properties_gdf['mod_date'].astype(str)
    # --- END PRE-PROCESSING ---
    
    # Remainder of the Logic (Error Check and Map Generation)
    
    if community_properties_gdf.empty:
        long_comm_name = community_boundary.iloc[0]['name'] 
        return Response(f'{{"error": "No property data found for community: {long_comm_name}."}}', 
                        status=404, 
                        mimetype='application/json')
        
    # Step 4: Extract the correct long name for the map title/header
    long_comm_name = community_properties_gdf['comm_name'].iloc[0]

    # Convert to standard CRS (WGS84) for Folium
    community_properties_gdf = community_properties_gdf.to_crs(epsg=4326)
    community_boundary = community_boundary.to_crs(epsg=4326)

    # Define a projected CRS (UTM Zone 11N) for accurate geometric calculations
    PROJECTED_CRS = 32611

    # --- FIX 1: ACCURATE CENTROID CALCULATION (Removes UserWarning) ---
    # Reproject the boundary to the PROJected CRS temporarily
    projected_boundary = community_boundary.to_crs(epsg=PROJECTED_CRS)
    
    # 2. Calculate the centroid (resulting GeoSeries is still in PROJECTED_CRS)
    centroid_series_proj = projected_boundary.geometry.centroid

    # 3. Apply the CRS transformation to the GeoSeries
    # This must be done on the GeoSeries, not the Point object itself
    centroid_series_4326 = centroid_series_proj.to_crs(epsg=4326)

    # 4. Extract the single Point geometry object from the GeoSeries
    centroid_point = centroid_series_4326.iloc[0]

    # Calculate map center and create the base Folium map
    # Extract the X (longitude) and Y (latitude) from the final Point object
    map_center = [centroid_point.y, centroid_point.x] 
    community_map = folium.Map(location=map_center, zoom_start=13)

    # Add Community Boundary to the map
    folium.GeoJson(
        community_boundary.to_json(),
        name=f"Boundary: {long_comm_name}",
        style_function=lambda x: {'fillColor': '#007bff', 'color': 'black', 'weight': 2, 'fillOpacity': 0.1}
    ).add_to(community_map)

    # --- FIX 2: MEMORY OPTIMIZATION VIA COLUMN SLICING ---
    # Only select the columns absolutely necessary for the GeoJSON output (geometry + tooltip/popup fields)
    columns_for_export = [
        'geometry', 
        'address', 
        'assessment_class_description', 
        'formatted_assessed_values'
        # Add 'mod_date' here if you want it available for popups
    ]
    properties_for_export = community_properties_gdf[columns_for_export]

    # Add the filtered and optimized properties to the map
    # This line now uses a much smaller GeoJSON string, reducing memory pressure during serialization
    folium.GeoJson(
        properties_for_export.to_json(), # Use the optimized GDF
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
        highlight_function=lambda x: {'fillColor': '#ffff00', 'color': '#000000', 'fillOpacity': 0.50, 'weight': 0.1},
        tooltip_anchor='right'
    ).add_to(community_map)


    # Add Layer Control
    folium.LayerControl().add_to(community_map) 

    map_html = community_map._repr_html_()

    # Wrap the map HTML with the community name for the client-side script
    response_data = {
        "map_html": map_html,
        "community_name": long_comm_name
    }
    return Response(json.dumps(response_data), mimetype='application/json')

    # # Pass the long name and map to the template
    # return render_template('map.html', map_html=map_html, community_name=long_comm_name)

if __name__ == '__main__':
    # Get the port from the environment variable $PORT,
    # or default to 5000 for local testing.
    port = int(os.environ.get('PORT', 5000))
    
    # Run the app, binding to 0.0.0.0 and the retrieved port.
    app.run(host='0.0.0.0', port=port)

    # app.run(debug=True, host='0.0.0.0', port=5000)