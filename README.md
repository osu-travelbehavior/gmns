# GMNS Network Merge Tool

This project merges two different networks (e.g., for different modes of transport) or two separate datasets of the same mode into a single, integrated GMNS (General Modeling Network Specification) network.

## 📌 Network Definitions & Recommendations
Before merging, it is recommended to define your two networks as follows:
* **Base Network (`base_node_df`, `base_link_df`)**: A highly accessible and dense network, such as a road or pedestrian network. It is recommended to use the primary network containing zone centroids and existing connector information as the base.
* **Merge Network (`merge_node_df`, `merge_link_df`)**: A network with lower spatial accessibility but higher mobility, such as a railway or public transit network. It is recommended to use a sub-network lacking zone centroids or connector information for this.

---

## 1. `network_merge_update.ipynb`
Prepares the two networks for merging by unifying the node and link ID systems to prevent conflicts, and updates the origin and destination nodes of each link to match the new IDs.

* **Main Function**: `network_update()`
* **Input Parameters**:
    * `base_node_df` (DataFrame): Node data of the base network.
    * `base_link_df` (DataFrame): Link data of the base network.
    * `merge_node_df` (DataFrame): Node data of the network to be merged.
    * `merge_link_df` (DataFrame): Link data of the network to be merged.
* **How it works**: Reassigns the IDs of the merge network sequentially, starting right after the maximum ID of the base network. (Original IDs are safely preserved in the `old_node_id` and `old_link_id` columns).
* **Returns**: Four updated DataFrames (`updated_base_node_df`, `updated_merge_node_df`, `updated_base_link_df`, `updated_merge_link_df`).

## 2. `network_merge_connector_generation.ipynb`
Generates virtual 'transfer connector' links that physically and logically connect the two networks. These connectors allow seamless routing between the different transportation modes.

* **Main Function**: `transfer_connector_builder()`
* **Input Parameters**:
    * `base_node_df` (DataFrame): Base network nodes.
    * `merge_node_df` (DataFrame): Merge network nodes to be connected.
    * `search_radius` (float, default `1000`): Maximum search radius in meters to find the closest node.
    * `filter_node_type` (str, default `None`): Optional parameter to filter and create connectors only for a specific node type (e.g., `'bus_service_node'`).
* **How it works**: Uses a cKDTree for spatial searching and the Haversine formula for accurate distance calculation to connect the closest nodes within the specified radius using bidirectional links.
* **Returns**: A DataFrame containing the generated transfer connector information (`connector_df`).

## 3. `network_merge_final.ipynb`
Finally merges the updated networks and the newly generated connector links, sorting the combined network into a Forward Star structure to optimize future shortest-path algorithms.

* **Main Function**: `network_merge()`
* **Input Parameters**:
    * `updated_base_node_df`, `updated_base_link_df`: Base data returned from Step 1.
    * `updated_merge_node_df`, `updated_merge_link_df`: Merge data returned from Step 1.
    * `connector_df`: Connector data generated in Step 2.
    * `base_link_allowed_uses` (str, default `None`): Specify a string value to batch-overwrite the `allowed_uses` attribute for base links.
    * `merge_link_allowed_uses` (str, default `None`): Specify a string value to batch-overwrite the `allowed_uses` attribute for merge links.
* **How it works**: Concatenates (`pd.concat`) all nodes and links into a single DataFrame, maps the connector link IDs sequentially, and finally sorts the links in ascending order based on origin and destination nodes (`from_node_id`, `to_node_id`).
* **Returns**: The final, integrated single network DataFrames (`merged_node_df`, `merged_link_df`).
