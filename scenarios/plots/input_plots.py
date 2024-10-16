import powergama
import pathlib
import folium
import pandas as pd
import os

# This script reads and plots input data for the PowerGAMA model. The plots are saved in the folder input_plots.

year=2020
def read_data(year):
    scenario_power_syst_data = pathlib.Path(f"../data/nordic/data_{year}")
    file_storval_filling = pathlib.Path(f"../data/nordic/data_storagevalues/profiles_storval_filling.csv")
    file_30y_profiles = pathlib.Path(f"../data/nordic/data_timeseries/timeseries_profiles/timeseries_profiles.csv")

    # Direkte fra raw filen over powerplants fra powerplantmatching. Brukt for å plotte powerplants på kartet med riktig lat long posisjon.
    powerplants = pd.read_csv(f"../data/All_powerplant_powerplantmatching.csv")
    nordic_powerplants = powerplants[powerplants['Country'].isin(['Norway', 'Sweden', 'Finland'])]

    data = powergama.GridData()
    data.readGridData(nodes=scenario_power_syst_data/"node.csv",
                        ac_branches=scenario_power_syst_data/"branch.csv",
                        dc_branches=scenario_power_syst_data/"dcbranch.csv",
                        generators=scenario_power_syst_data/"generator.csv",
                        consumers=scenario_power_syst_data/"consumer.csv")

    return scenario_power_syst_data, data, nordic_powerplants, file_storval_filling, file_30y_profiles
scenario_power_syst_data, data, nordic_powerplants, file_storval_filling, file_30y_profiles = read_data(year)

def node_plot():
    # Nodes
    node_file = scenario_power_syst_data / "node.csv"
    nodes_df = pd.read_csv(node_file)
    mean_lat_nodes = nodes_df['lat'].mean()
    mean_lon_nodes = nodes_df['lon'].mean()

    # Production and consumption in each node
    consumers_file = scenario_power_syst_data / "consumer.csv"
    producers_file = scenario_power_syst_data / "generator.csv"
    consumers_df = pd.read_csv(consumers_file)
    producers_df = pd.read_csv(producers_file)

    consumers_with_location = pd.merge(consumers_df, nodes_df[['id', 'lat', 'lon']], left_on='node', right_on='id')
    producers_with_location = pd.merge(producers_df, nodes_df[['id', 'lat', 'lon']], left_on='node', right_on='id')
    map_production_consumption = folium.Map(location=[mean_lat_nodes, mean_lon_nodes], zoom_start=5)

    for idx, row in nodes_df.iterrows():
        # Finn forbruk og produksjon for noden (om de finnes)
        consumption = consumers_with_location[consumers_with_location['node'] == row['id']]['demand_avg'].sum()
        production = producers_with_location[producers_with_location['node'] == row['id']]['pmax'].sum()

        # Popup som viser både produksjon og forbruk, formatert og med bredde satt til 300 px
        popup_text = (
            f"<b>Node:</b> {row['id']}<br>"
            f"<b>Average demand:</b> {consumption:.3f} MW<br>"
            f"<b>Installed capacity:</b> {production:.3f} MW"
        )

        popup = folium.Popup(popup_text, max_width=300)

        folium.Marker(
            location=[row['lat'], row['lon']],
            popup=popup,
        ).add_to(map_production_consumption)

    # Plotting av linjer mellom noder (branches)
    branches_file = scenario_power_syst_data / "branch.csv"
    branches_df = pd.read_csv(branches_file)

    # Merge for å hente koordinater for node_from og node_to
    branches_with_coords = branches_df.merge(nodes_df[['id', 'lat', 'lon']], left_on='node_from', right_on='id', suffixes=('', '_from'))
    branches_with_coords = branches_with_coords.merge(nodes_df[['id', 'lat', 'lon']], left_on='node_to', right_on='id', suffixes=('', '_to'))

    # Plot linjer mellom noder
    for idx, row in branches_with_coords.iterrows():
        popup_text = (
            f"<b>Branch:</b> {row['node_from']} - {row['node_to']}<br>"
            f"<b>Capacity:</b> {row['capacity']:.3f} MW"
        )
        popup = folium.Popup(popup_text, max_width=300)

        # Legg til linje med popup (ingen ekstra markør)
        folium.PolyLine(
            locations=[[row['lat'], row['lon']], [row['lat_to'], row['lon_to']]],  # Fra node_from til node_to
            color='red',
            weight=2,
            popup=popup  # Popup når du klikker på linjen
        ).add_to(map_production_consumption)

    map_production_consumption.save(os.path.join('input_plots', 'production_consumption_map.html'))
node_plot()

def prod_distribution():
    # Geographic distribution of producers and their capacity
    mean_lat_prod = nordic_powerplants['lat'].mean()
    mean_lon_prod = nordic_powerplants['lon'].mean()
    map_prod = folium.Map(location=[mean_lat_prod, mean_lon_prod], zoom_start=5)

    for idx, row in nordic_powerplants.iterrows():
        # Create blue circles for producers with size depending on capacity
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=row['Capacity'] / 100,  # Scale the radius by capacity (adjust if necessary)
            color='blue',
            fill=True,
            fill_color='blue',
            fill_opacity=0.6,
            popup=f"Producer Capacity: {row['Capacity']} MW"
        ).add_to(map_prod)
    map_prod.save(os.path.join('input_plots', 'powergrid_producers_map.html'))                                           # Save the map as an HTML file
prod_distribution()

