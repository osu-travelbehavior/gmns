"""GMNS network merging and connector generation.

Functions extracted from https://github.com/osu-travelbehavior/gmns.
"""

import os

import numpy as np
import pandas as pd
from geopy.distance import geodesic
from scipy.spatial import cKDTree
from shapely.geometry import LineString
from shapely.wkt import dumps

__all__ = [
    "DEFAULT_CONNECTOR_CONFIG",
    "network_update",
    "transfer_connector_builder",
    "network_merge",
    "process_node_data",
    "generate_connector_links",
    "update_and_merge_links",
    "create_updated_node_df"
]

def network_update(
    base_node_df: pd.DataFrame,
    base_link_df: pd.DataFrame,
    merge_node_df: pd.DataFrame,
    merge_link_df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Integrates and updates node and link IDs from a base network and a network to be merged.

    Args:
        base_node_df (pd.DataFrame): DataFrame of nodes for the base network.
        base_link_df (pd.DataFrame): DataFrame of links for the base network.
        merge_node_df (pd.DataFrame): DataFrame of nodes for the network to be merged.
        merge_link_df (pd.DataFrame): DataFrame of links for the network to be merged.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
            A tuple containing:
            - updated_base_node_df (pd.DataFrame): Updated base node DataFrame.
            - updated_merge_node_df (pd.DataFrame): Updated merged node DataFrame.
            - updated_base_link_df (pd.DataFrame): Updated base link DataFrame.
            - updated_merge_link_df (pd.DataFrame): Updated merged link DataFrame.
    """

    # 1. Integrate and Update Node IDs
    # Save existing node_id to 'old_node_id' column for both base and merge dataframes.
    # If 'old_node_id' already exists, it will be overwritten.
    base_node_df['old_node_id'] = base_node_df['node_id']
    merge_node_df['old_node_id'] = merge_node_df['node_id']

    # Base network's node_ids remain as they are (assuming they start from 1).
    # New node_ids for the merged network start after the maximum node_id of the base network.
    num_rows_in_base_df = len(base_node_df) # Get the total number of rows (nodes) in the base DataFrame.
    max_node_id_in_base_df = base_node_df['node_id'].max() # Get the maximum value in the 'node_id' column.

    # Compare the max_node_id with the number of rows.
    # If they are not equal, the node_ids are not sequential from 1.
    is_base_renumbering_needed = (max_node_id_in_base_df != num_rows_in_base_df)
    if is_base_renumbering_needed:
        print(f"base_node_df: Max ID ({max_node_id_in_base_df}) != Row count ({num_rows_in_base_df}). Renumbering required.")
        # Sort the DataFrame by the existing 'node_id' to maintain a logical order.
        sorted_base_df = base_node_df.sort_values(by='node_id')
        # Reset the index of the sorted DataFrame to ensure it's clean (0, 1, 2, ...).
        reset_base_df = sorted_base_df.reset_index(drop=True)
        # Create a new array of sequential numbers, from 1 to the number of rows.
        new_sequential_ids_for_base = np.arange(1, num_rows_in_base_df + 1)
        
        # Assign the new sequential IDs to the 'node_id' column.
        # We use .copy() to avoid potential pandas SettingWithCopyWarning.
        base_node_df = reset_base_df.copy()
        base_node_df['node_id'] = new_sequential_ids_for_base


    num_rows_in_merge_df = len(merge_node_df) # Get the total number of rows (nodes) in the merge DataFrame.
    max_node_id_in_merge_df = merge_node_df['node_id'].max() # Get the maximum value in the 'node_id' column.

    # Compare the max_node_id with the number of rows.
    is_merge_renumbering_needed = (max_node_id_in_merge_df != num_rows_in_merge_df)
    if is_merge_renumbering_needed:
        print(f"merge_node_df: Max ID ({max_node_id_in_merge_df}) != Row count ({num_rows_in_merge_df}). Renumbering required.")
        # Sort, reset index, and create new sequential IDs.
        sorted_merge_df = merge_node_df.sort_values(by='node_id')
        reset_merge_df = sorted_merge_df.reset_index(drop=True)
        new_sequential_ids_for_merge = np.arange(1, num_rows_in_merge_df + 1)
        
        # Assign the new IDs.
        merge_node_df = reset_merge_df.copy()
        merge_node_df['node_id'] = new_sequential_ids_for_merge

    max_base_node_id = base_node_df['node_id'].max()
    merge_node_df['node_id'] = merge_node_df['node_id'] + max_base_node_id

    # Create a node ID mapping dictionary (old_node_id -> new_node_id)
    # For the base network
    node_id_map = pd.Series(base_node_df['node_id'].values, index=base_node_df['old_node_id']).to_dict()
    # For the merge network
    merge_node_id_map = pd.Series(merge_node_df['node_id'].values, index=merge_node_df['old_node_id']).to_dict()
    

    # 2. Integrate and Update Link IDs
    # Save existing link_id to 'old_link_id' column for both base and merge dataframes.
    # If 'old_link_id' already exists, it will be overwritten.
    base_link_df['old_link_id'] = base_link_df['link_id']
    merge_link_df['old_link_id'] = merge_link_df['link_id']

    num_rows_in_base_link_df = len(base_link_df) # Get the total number of rows (links) in the base DataFrame.
    max_link_id_in_base_link_df = base_link_df['link_id'].max() # Get the maximum value in the 'link_id' column.

    # Compare the max_link_id with the number of rows.
    # If they are not equal, the link_ids are not sequential from 1.
    is_base_link_renumbering_needed = (max_link_id_in_base_link_df != num_rows_in_base_link_df)

    if is_base_link_renumbering_needed:
        print(f"base_link_df: Max ID ({max_link_id_in_base_link_df}) != Row count ({num_rows_in_base_link_df}). Renumbering required.")
        
        # Sort the DataFrame by the existing 'link_id' to maintain a logical order.
        sorted_base_link_df = base_link_df.sort_values(by='link_id')
        
        # Reset the index of the sorted DataFrame to ensure it's clean (0, 1, 2, ...).
        reset_base_link_df = sorted_base_link_df.reset_index(drop=True)
        
        # Create a new array of sequential numbers, from 1 to the number of rows.
        new_sequential_ids_for_base_link = np.arange(1, num_rows_in_base_link_df + 1)
        
        # Assign the new sequential IDs to the 'link_id' column.
        # We use .copy() to avoid potential pandas SettingWithCopyWarning.
        base_link_df = reset_base_link_df.copy()
        base_link_df['link_id'] = new_sequential_ids_for_base_link

    num_rows_in_merge_link_df = len(merge_link_df) # Get the total number of rows (links) in the merge DataFrame.
    max_link_id_in_merge_link_df = merge_link_df['link_id'].max() # Get the maximum value in the 'link_id' column.

    # Compare the max_link_id with the number of rows.
    is_merge_link_renumbering_needed = (max_link_id_in_merge_link_df != num_rows_in_merge_link_df)

    if is_merge_link_renumbering_needed:
        print(f"merge_link_df: Max ID ({max_link_id_in_merge_link_df}) != Row count ({num_rows_in_merge_link_df}). Renumbering required.")
        
        # Sort, reset index, and create new sequential IDs.
        sorted_merge_link_df = merge_link_df.sort_values(by='link_id')
        reset_merge_link_df = sorted_merge_link_df.reset_index(drop=True)
        new_sequential_ids_for_merge_link = np.arange(1, num_rows_in_merge_link_df + 1)
        
        # Assign the new IDs.
        merge_link_df = reset_merge_link_df.copy()
        merge_link_df['link_id'] = new_sequential_ids_for_merge_link

    # New link_ids for the merged network start after the maximum link_id of the base network.
    max_base_link_id = base_link_df['link_id'].max()
    merge_link_df['link_id'] = merge_link_df['link_id'] + max_base_link_id

    # 3. Update from_node_id and to_node_id in Link Files
    # Update base link file using the node ID map
    base_link_df['from_node_id'] = base_link_df['from_node_id'].map(node_id_map)
    base_link_df['to_node_id'] = base_link_df['to_node_id'].map(node_id_map)

    # Update merged link file using the node ID map
    merge_link_df['from_node_id'] = merge_link_df['from_node_id'].map(merge_node_id_map)
    merge_link_df['to_node_id'] = merge_link_df['to_node_id'].map(merge_node_id_map)

    return base_node_df, merge_node_df, base_link_df, merge_link_df


def transfer_connector_builder(
    base_node_df: pd.DataFrame,
    merge_node_df: pd.DataFrame,
    search_radius: float = 1000, # Default search radius in meters
    filter_node_type: str = None
) -> pd.DataFrame:
    """
    Builds connector links between the closest nodes of a base network and a merge network.
    It creates bidirectional links and includes various link attributes.

    Args:
        base_node_df (pd.DataFrame): DataFrame of nodes for the base network.
                                     Must contain 'node_id', 'x_coord', 'y_coord' columns.
        merge_node_df (pd.DataFrame): DataFrame of nodes for the network to be merged.
                                      Must contain 'node_id', 'x_coord', 'y_coord' columns.
        search_radius (float): The maximum distance (in meters) to search for a
                               closest base node for each merge node. Defaults to 1000 meters.
        filter_node_type (str, optional): The type of node to filter in merge_node_df (e.g., 'bus_service_node'). 
                                          If None, no filtering is applied. Defaults to None.

    Returns:
        pd.DataFrame: A DataFrame containing the generated connector links with all specified attributes.
                      Returns an empty DataFrame if no connectors are found or input DataFrames are invalid.
    """

    # Validate input DataFrames
    required_cols = ['node_id', 'x_coord', 'y_coord']
    if not all(col in base_node_df.columns for col in required_cols):
        print(f"Error: base_node_df is missing required columns. Ensure it has {required_cols}")
        return pd.DataFrame()
    if not all(col in merge_node_df.columns for col in required_cols):
        print(f"Error: merge_node_df is missing required columns. Ensure it has {required_cols}")
        return pd.DataFrame()
    
    # Select node_type to filter nodes for connector building
    if filter_node_type is not None:
        if 'node_type' in merge_node_df.columns:
            merge_node_df = merge_node_df[merge_node_df['node_type'] == filter_node_type]
            merge_node_df = merge_node_df.reset_index(drop=True)
        else:
            print(f"Warning: 'node_type' column is missing in merge_node_df. Skipping filter.")

    # Prepare coordinates for spatial search
    # Assuming x_coord is longitude and y_coord is latitude for haversine distance
    base_coords = base_node_df[['x_coord', 'y_coord']].to_numpy()
    merge_coords = merge_node_df[['x_coord', 'y_coord']].to_numpy()

    # Use cKDTree for efficient nearest neighbor search
    # This will find the closest base node for each merge node
    tree = cKDTree(base_coords)
    # query returns: distances, indices
    # distances are in the same unit as the coordinates, which are degrees
    # We divide by 111320.0 (approx meters per degree at equator) to convert search_radius to degrees.
    # This is a rough approximation for initial candidate filtering; for more accurate distance,
    # Haversine formula is needed *after* finding candidates.
    distances_deg, base_node_indices = tree.query(merge_coords, k=1, distance_upper_bound=search_radius / 111320.0)
    
    connector_links_data = []
    current_link_id = 1
    R = 6371000 # Earth radius in meters

    for i, (merge_node_id, merge_x, merge_y) in merge_node_df[['node_id', 'x_coord', 'y_coord']].iterrows():
        # Check if a candidate base node was found within the approximate radius
        if base_node_indices[i] < len(base_node_df): # Ensure index is valid (not infinity from distance_upper_bound)
            closest_base_node_idx = base_node_indices[i]
            base_node_id = base_node_df.iloc[closest_base_node_idx]['node_id']
            base_x = base_node_df.iloc[closest_base_node_idx]['x_coord']
            base_y = base_node_df.iloc[closest_base_node_idx]['y_coord']

            # Calculate precise Haversine distance in meters
            # Convert degrees to radians
            lat1, lon1, lat2, lon2 = map(np.radians, [merge_y, merge_x, base_y, base_x])
            dlon = lon2 - lon1
            dlat = lat2 - lat1
            a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
            c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
            length_meters = R * c

            # Filter by actual search radius in meters
            if length_meters <= search_radius:
                # Create bidirectional connector links

                # Connector: Merge Node -> Base Node
                geometry_wkt_1 = dumps(LineString([(merge_x, merge_y), (base_x, base_y)]))
                connector_links_data.append({
                    "link_id": current_link_id,
                    "name": "",
                    "from_node_id": merge_node_id,
                    "to_node_id": base_node_id,
                    "directed": 1,
                    "geometry": geometry_wkt_1,
                    "dir_flag": 1,
                    "length": length_meters,
                    "lanes": 1,
                    "free_speed": 120,
                    "capacity": 100000,
                    "link_type_name": "connector",
                    "link_type": 0,
                    "allowed_uses": "bike",
                    "from_biway": 1,
                    "is_link": 0,
                    "vdf_toll": 0,
                    "vdf_alpha": 0.15,
                    "vdf_beta": 4,
                    "vdf_plf": 1,
                    "vdf_length_mi": length_meters / 1609.344,
                    "vdf_free_speed_mph": 120/1.609344
                })
                current_link_id += 1

                # Connector: Base Node -> Merge Node (reverse direction)
                geometry_wkt_2 = dumps(LineString([(base_x, base_y), (merge_x, merge_y)]))
                connector_links_data.append({
                    "link_id": current_link_id,
                    "name": "",
                    "from_node_id": base_node_id,
                    "to_node_id": merge_node_id,
                    "directed": 1,
                    "geometry": geometry_wkt_2,
                    "dir_flag": 1,
                    "length": length_meters,
                    "lanes": 1,
                    "free_speed": 120,
                    "capacity": 100000,
                    "link_type_name": "connector",
                    "link_type": 0,
                    "allowed_uses": "bike",
                    "from_biway": 1,
                    "is_link": 0,
                    "vdf_toll": 0,
                    "vdf_alpha": 0.15,
                    "vdf_beta": 4,
                    "vdf_plf": 1,
                    "vdf_length_mi": length_meters / 1609.344,
                    "vdf_free_speed_mph": 120/1.609344
                })
                current_link_id += 1
    
    if not connector_links_data:
        print("No connector links found within the specified search radius.")
        return pd.DataFrame()

    connector_df = pd.DataFrame(connector_links_data)

    # Calculate 'vdf_free_speed_in_mph'
    connector_df['vdf_free_speed_in_mph'] = connector_df['free_speed'] / 1.609344

    # Calculate 'vdf_fftt'
    # Note: free_speed can be 0, which would result in division by zero (infinity)
    connector_df['vdf_fftt'] = (connector_df['length'] / 1000) / connector_df['free_speed'] * 60

    # Handle potential infinite values resulting from division by zero
    # We replace infinity (inf) with 0, a common practice for impassable links
    connector_df.replace([np.inf, -np.inf], 0, inplace=True)


    return connector_df


def network_merge(
    updated_base_node_df: pd.DataFrame,
    updated_base_link_df: pd.DataFrame,
    updated_merge_node_df: pd.DataFrame,
    updated_merge_link_df: pd.DataFrame,
    connector_df: pd.DataFrame,
    base_link_allowed_uses: str = None, # Changed default to None
    merge_link_allowed_uses: str = None  # Changed default to None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Merges updated base and merge network DataFrames, including connector links.
    Allows for optional overwriting of 'allowed_uses' for base and merge links.

    Args:
        updated_base_node_df (pd.DataFrame): Updated node DataFrame for the base network.
        updated_base_link_df (pd.DataFrame): Updated link DataFrame for the base network.
        updated_merge_node_df (pd.DataFrame): Updated node DataFrame for the network to be merged.
        updated_merge_link_df (pd.DataFrame): Updated link DataFrame for the network to be merged.
        connector_df (pd.DataFrame): DataFrame containing the generated connector links.
        base_link_allowed_uses (str, optional): String value to set for the 'allowed_uses' column
                                                of links from the base network. If None (default),
                                                the existing 'allowed_uses' values are kept.
        merge_link_allowed_uses (str, optional): String value to set for the 'allowed_uses' column
                                                 of links from the merged network. If None (default),
                                                 the existing 'allowed_uses' values are kept.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]:
            A tuple containing:
            - merged_node_df (pd.DataFrame): The combined node DataFrame.
            - merged_link_df (pd.DataFrame): The combined link DataFrame.
    """

    # 1. Merge Node DataFrames
    # Concatenate the updated base and merge node dataframes.
    # We use .copy() to ensure we're working with independent copies to avoid SettingWithCopyWarning
    merged_node_df = pd.concat(
    [updated_base_node_df.copy(), updated_merge_node_df.copy()],
    ignore_index=True,  # new index
    join='outer')

    # 2. Update 'allowed_uses' for base and merge links
    # Apply the specified allowed_uses string to the respective link dataframes if not None.
    if base_link_allowed_uses is not None:
        updated_base_link_df['allowed_uses'] = base_link_allowed_uses
    # Else, if base_link_allowed_uses is None, the original values are preserved.

    if merge_link_allowed_uses is not None:
        updated_merge_link_df['allowed_uses'] = merge_link_allowed_uses
    # Else, if merge_link_allowed_uses is None, the original values are preserved.


    # 3. Update link_id for connector links
    # Connector link_ids should start from (max_link_id from base/merge links) + 1.
    max_existing_link_id = max(updated_base_link_df['link_id'].max(), updated_merge_link_df['link_id'].max())

    # Only update connector_df if it's not empty, and it has 'link_id'
    if not connector_df.empty and 'link_id' in connector_df.columns:
        # Increment the existing connector link_ids by max_existing_link_id
        # This assumes connector_df's link_ids are already sequential from 1
        connector_df['link_id'] = connector_df['link_id'] + max_existing_link_id
    elif not connector_df.empty and 'link_id' not in connector_df.columns:
        print("Warning: 'link_id' column not found in connector_df. Connector link IDs will not be re-indexed.")
    
    # 4. Merge Link Dataframes
    # Concatenate the updated base links, updated merge links, and the adjusted connector links.
    merged_link_df = pd.concat(
    [
        updated_base_link_df.copy().reset_index(drop=True),
        updated_merge_link_df.copy().reset_index(drop=True),
        connector_df.copy().reset_index(drop=True)
    ],
    ignore_index=True,
    join='outer')

    merged_link_df = merged_link_df.sort_values(
        by=["from_node_id", "to_node_id"], 
        ascending=True
    ).reset_index(drop=True)

    merged_link_df['link_id'] = range(1, len(merged_link_df) + 1)

    return merged_node_df, merged_link_df


DEFAULT_CONNECTOR_CONFIG = {
    "dir_flag": 1,
    "lanes": 1,
    "free_speed": 5,
    "capacity": 10000,
    "link_type_name": "connector",
    "link_type": 0,
    "allowed_uses": "walk",
    "from_biway": 1,
    "is_link": 0,
    "vdf_toll": 0,
    "vdf_alpha": 0.15,
    "vdf_beta": 4,
    "vdf_plf": 1,
}

def process_node_data(node_df, node_taz_df, output_path=None):
    try:
        print("Starting to process node data...")

        # Step 1: Find the maximum node_id in node_taz_df
        print("Finding the maximum node_id in node_taz_df...")
        max_node_id_taz = node_taz_df['zone_id'].max()
        min_node_id = node_df['node_id'].min()
        print(f"Maximum node_id in node_taz_df: {max_node_id_taz}")

        # Step 2: Add (max_node_id_taz + 1) to all node_ids in node_df
        print("Adding new_node_id to node_df...")
        node_df['new_node_id'] = node_df['node_id'] + max_node_id_taz - min_node_id + 1
        print("New node_id generation completed.")
        return node_df

    except Exception as e:
        print(f"An error occurred while processing node data: {e}")

def generate_connector_links(updated_node_df, node_taz_df, output_path=None, n_connector=3, node_types=None,
    connector_config=None):
    try:
        print("Starting to generate connector links...")

        # Set default configuration
        if connector_config is None:
            connector_config = DEFAULT_CONNECTOR_CONFIG.copy()

        # Force x/y coordinate columns to be float
        updated_node_df[['x_coord', 'y_coord']] = updated_node_df[['x_coord', 'y_coord']].astype(float)
        node_taz_df[['x_coord', 'y_coord']] = node_taz_df[['x_coord', 'y_coord']].astype(float)
        
        connector_links = []
        total_length = 0
        pair_number = 0
        print(updated_node_df['node_type'].unique())

        # Filter node type only when specified (Modified May 12, 2026)
        if node_types is not None:
            updated_node_df = updated_node_df[
            updated_node_df['node_type'].isin(node_types)]

        for idx, taz_node in node_taz_df.iterrows():
            taz_node_id = taz_node['zone_id']
            taz_node_x = taz_node['x_coord']
            taz_node_y = taz_node['y_coord']

            updated_node_df['distance'] = np.sqrt(
                (updated_node_df['x_coord'] - taz_node_x) ** 2 +
                (updated_node_df['y_coord'] - taz_node_y) ** 2
            )

            # nearest # nodes
            nearest_nodes = updated_node_df.nsmallest(n_connector, 'distance')
            for _, nearest_node in nearest_nodes.iterrows():

                nearest_node_id = nearest_node['new_node_id']
                nearest_node_x = nearest_node['x_coord']
                nearest_node_y = nearest_node['y_coord']

                for from_id, to_id, from_x, from_y, to_x, to_y in [
                    (nearest_node_id, taz_node_id, nearest_node_x, nearest_node_y, taz_node_x, taz_node_y),
                    (taz_node_id, nearest_node_id, taz_node_x, taz_node_y, nearest_node_x, nearest_node_y)
                ]:

                    geometry = f"LINESTRING ({from_x} {from_y}, {to_x} {to_y})"

                    length = geodesic(
                        (from_y, from_x),
                        (to_y, to_x)
                    ).meters

                    connector_links.append({
                        "link_id": len(connector_links) + 1,
                        "from_node_id": from_id,
                        "to_node_id": to_id,
                        "length": length,
                        "geometry": geometry,
                        **connector_config
                    })

        connector_links_df = pd.DataFrame(connector_links)
        print(f"Generated {len(connector_links_df)} connector links.")

        connector_links_df["vdf_toll"] = (connector_config["vdf_toll"])
        connector_links_df["allowed_uses"] = (connector_config["allowed_uses"])
        connector_links_df["vdf_alpha"] = (connector_config["vdf_alpha"])
        connector_links_df["vdf_beta"] = (connector_config["vdf_beta"])
        connector_links_df["vdf_plf"] = (connector_config["vdf_plf"])
        connector_links_df["vdf_length_mi"] = connector_links_df["length"] / 1609
        connector_links_df["vdf_free_speed_mph"] = connector_links_df["free_speed"] / 1.60934
        connector_links_df["free_speed_in_mph_raw"] = round(connector_links_df["vdf_free_speed_mph"] / 5) * 5
        connector_links_df["vdf_fftt"] = (connector_links_df["length"] / connector_links_df["free_speed"]) * 0.06

        other_columns = ['ref_volume', 'base_volume', 'base_vol_auto', 'restricted_turn_nodes']
        for other_column in other_columns:
            connector_links_df[other_column] = None

        file_name = "connector_links.csv"
        output_file = os.path.join(output_path, file_name)
        if output_file:
            connector_links_df.to_csv(output_file, index=False)
            print(f"The connector links have been successfully saved to '{output_file}'.")
        else:
            print("Output file not provided. Skipping file saving.")

        return connector_links_df

    except Exception as e:
        print(f"An error occurred while generating connector links: {e}")

def update_and_merge_links(link_df, updated_node_df, connector_links_df, output_path):
    """
    Updates link_df with new_node_id, merges it with connector_links_df, and saves the updated file.

    Args:
        link_df (pd.DataFrame): DataFrame containing the original link data.
        node_df (pd.DataFrame): DataFrame containing node_id and new_node_id mapping.
        connector_links_df (pd.DataFrame): DataFrame containing the connector links.
        output_file (str): Path to save the updated Link_Updated.csv file.
    """
    try:
        # Step 1: Create a mapping of node_id to new_node_id
        node_id_map = dict(zip(updated_node_df['node_id'], updated_node_df['new_node_id']))

        # Step 2: Update from_node_id and to_node_id in link_df
        link_df['from_node_id'] = link_df['from_node_id'].map(node_id_map)
        link_df['to_node_id'] = link_df['to_node_id'].map(node_id_map)

        # Step 3: Validate if there are any unmatched IDs
        if link_df['from_node_id'].isnull().any() or link_df['to_node_id'].isnull().any():
            print("Warning: Some from_node_id or to_node_id in link_df could not be mapped to new_node_id.")

        # Step 3.5: Add new column to link_df
        # Step3.5 Add new columns
        link_df["vdf_toll"] = 0
        link_df["allowed_uses"] = 'bike'
        link_df["vdf_alpha"] = 0.15
        link_df["vdf_beta"] = 4
        link_df["vdf_plf"] = 1
        link_df["vdf_length_mi"] = link_df["length"] / 1609
        link_df["vdf_free_speed_mph"] = link_df["free_speed"] / 1.60934
        link_df["free_speed_in_mph_raw"] = round(link_df["vdf_free_speed_mph"] / 5) * 5
        link_df["vdf_fftt"] = (link_df["length"] / link_df["free_speed"]) * 0.06

        other_columns = ['ref_volume', 'base_volume', 'base_vol_auto', 'restricted_turn_nodes']
        for other_column in other_columns:
            link_df[other_column] = None

        # Step 4: Align columns between link_df and connector_links_df
        all_columns = set(link_df.columns).union(connector_links_df.columns)

        # Add missing columns with None
        for col in all_columns:
            if col not in link_df.columns:
                link_df[col] = None
            if col not in connector_links_df.columns:
                connector_links_df[col] = None

        # Ensure connector_links_df has the same column order as link_df
        connector_links_df = connector_links_df[link_df.columns]
        # breakpoint()

        # Step 5: Combine link_df and connector_links_df
        combined_links_df = pd.concat([link_df, connector_links_df], ignore_index=True)

        # Step 6: Sort and assign new link_id
        combined_links_df = combined_links_df.sort_values(by=['from_node_id', 'to_node_id']).reset_index(drop=True)
        combined_links_df['link_id'] = range(1, len(combined_links_df) + 1)

        # Step 7: Save the updated DataFrame to the output file
        file_name = "link_updated.csv"
        output_file = os.path.join(output_path, file_name)
        combined_links_df.to_csv(output_file, index=False)
        print(f"Updated and merged data has been saved to {output_file}.")

    except Exception as e:
        print(f"An error occurred: {e}")

def create_updated_node_df(updated_node_df, node_taz_df, output_path):
    try:
        updated_node_df = updated_node_df.rename(columns={'node_id': 'old_node_id'})
        updated_node_df = updated_node_df.rename(columns={'new_node_id': 'node_id'})

        updated_node_df['zone_id'] = None
        node_taz_df['node_id'] = node_taz_df['zone_id']

        Node_Updated_df = pd.concat([node_taz_df, updated_node_df], ignore_index=True)
        Node_Updated_df = Node_Updated_df.sort_values(by=['node_id']).reset_index(drop=True)
        Node_Updated_df = Node_Updated_df.drop(columns=['ctrl_type', 'distance'])


        '''
        for i in range(len(Node_Updated_df)):
            if pd.isna(Node_Updated_df.loc[i, 'geometry']) or Node_Updated_df.loc[i, 'geometry'].strip() == '':
                x_coord = Node_Updated_df.loc[i, 'x_coord']
                y_coord = Node_Updated_df.loc[i, 'y_coord']
                Node_Updated_df.loc[i, 'geometry'] = f"POINT ({x_coord} {y_coord})"
        '''
        # 1. Extract rows where 'geometry' is NaN or empty string
        missing_geometry_df = Node_Updated_df[
        Node_Updated_df['geometry'].isna() | (Node_Updated_df['geometry'].str.strip() == '')
        ].copy()

        # 2. Remove those rows from the original DataFrame
        Node_Updated_df = Node_Updated_df.drop(missing_geometry_df.index)

        # 3. Fill 'geometry' column using 'x_coord' and 'y_coord'
        missing_geometry_df['geometry'] = missing_geometry_df.apply(
            lambda row: f"POINT ({row['x_coord']} {row['y_coord']})", axis=1
        )

        # 4. Concatenate the two DataFrames and sort by original index to preserve row order
        Node_Updated_df = pd.concat([Node_Updated_df, missing_geometry_df])
        Node_Updated_df = Node_Updated_df.sort_index()

        # 5. Delete the temporary DataFrame
        del missing_geometry_df

        file_name = "node_updated.csv"
        output_file = os.path.join(output_path, file_name)
        #Node_Updated_df = Node_Updated_df.drop(columns='zone_id', errors='ignore').rename(columns={'zone_id': 'zone_id'})
        
        #Important!! MOVE node_id to the 1st column
        Node_Updated_df = Node_Updated_df[['node_id'] + [c for c in Node_Updated_df.columns if c != 'node_id']]
        Node_Updated_df.to_csv(output_file, index=False)       
        print(f"The updated node data has been successfully saved to '{output_file}'.")
        return Node_Updated_df

    except Exception as e:
        print(f"An error occurred: {e}")

