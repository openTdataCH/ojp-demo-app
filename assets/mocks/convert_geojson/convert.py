import os, sys, json
from pathlib import Path

# from inc.common import load_app_config
# from inc.helpers.log_helpers import log_message
# from inc.helpers.ogr2ogr import OGR2OGR_Helpers

# from inc.geojson.feature_collection import FeatureCollection
# from inc.geojson.feature import Feature
# from inc.geojson.geometry.polygon import Polygon
# from inc.geojson.geometry.linestring import LineString
# from inc.geojson.geometry.multipolygon import MultiPolygon

def main():
    app_path = Path(os.path.realpath(__file__)).parent
    geojson_path = f'{app_path}/input.geojson'

    geojson_data_file = open(geojson_path, 'r')
    geojson_data = json.load(geojson_data_file)
    geojson_data_file.close()

    rows_coords = []
    f_json = geojson_data['features'][0]
    for pair_coords in f_json['geometry']['coordinates']:
        row_long = f'{pair_coords[0]}'
        row_lat = f'{pair_coords[1]}'
        row_coords = '<ojp:Position><siri:Longitude>' + row_long + '</siri:Longitude><siri:Latitude>' + row_lat + '</siri:Latitude></ojp:Position>'
        rows_coords.append(row_coords)
    
    print("\n".join(rows_coords))

    sys.exit()

    geojson_src_config = app_config['geodata']['swissBOUNDARIES3D_processed']
    geojson_dst_config = app_config['geodata']['swissBOUNDARIES3D_indexmap']

    geojson_src_base_path = geojson_src_config['geojson_base_path']

    # DONT COMMIT
    # merge_country_geometry(app_config)
    # sys.exit()

    for shape_type in geojson_src_config['map_paths']:
        log_message(f'START: - {shape_type} ...')

        geojson_src_path: str = geojson_src_config['map_paths'][shape_type]
        geojson_src_path = geojson_src_path.replace('[GEOJSON_BASE_PATH]', geojson_src_base_path)

        geojson_src_fc = FeatureCollection.init_from_file(geojson_src_path)
        features_no = len(geojson_src_fc.features)
        log_message(f'... found {features_no} features')

        # new_features: List[Feature] = []

        map_features = {}

        for feature in geojson_src_fc.features:
            new_geometry = massage_geometry_coords(feature)
            
            new_feature_properties = None
            if shape_type == 'country':
                feature_idx = len(map_features.keys()) + 1
                # The auto-index feature_id matters only for country
                new_feature_properties = massage_country_properties(feature, feature_idx)

            if shape_type == 'cantons':
                new_feature_properties = massage_canton_properties(feature)

            if shape_type == 'districts':
                new_feature_properties = massage_district_properties(feature)

            if shape_type == 'gemeinden':
                new_feature_properties = massage_municipality_properties(feature)

            if shape_type == 'limits-line':
                feature_idx = len(map_features.keys()) + 1
                new_feature_properties = massage_municipality_limits_properties(feature, feature_idx)

            if new_feature_properties == None:
                print(f'- skipping feature {feature.properties}')
                # This can happen only for country small parts (i.e. IT, DE islands)
                continue

            new_feature = Feature(new_geometry, new_feature_properties)

            feature_id = new_feature.properties['feature_id']
            
            # TODO - DON COMMIT
            # keep_feature_ids = [1, 10]
            # # keep_feature_ids = [10]
            # if not (feature_id in keep_feature_ids):
            #     continue

            if feature_id in map_features:
                prev_feature: Feature = map_features[feature_id]

                if isinstance(prev_feature.geometry, Polygon):
                    prev_feature.geometry = MultiPolygon.init_from_polygon(polygon=prev_feature.geometry)

                if not isinstance(prev_feature.geometry, MultiPolygon):
                    print('ERROR - massage polygons => expected MultiPolygon')
                    sys.exit(1)

                prev_feature_multipolygon: MultiPolygon = prev_feature.geometry
                prev_feature_multipolygon.add_polygon(new_feature.geometry)

                prev_feature_original_ids = prev_feature.properties['original_ids'].split(',')
                prev_feature_original_ids.append(new_feature.properties['original_ids'])

                prev_feature.properties['original_ids'] = ','.join(prev_feature_original_ids)
            else:
                map_features[feature_id] = new_feature

        new_features = list(map_features.values())
        geojson_dst_fc = FeatureCollection(new_features)
        geojson_dst_path: str = geojson_dst_config['map_paths'][shape_type]
        geojson_dst_fc.save_to_path(geojson_dst_path)

        log_message(f'... saved {len(new_features)} features to {geojson_dst_path}')

    # merge_country_geometry(app_config)

    log_message(f'DONE')

def merge_country_geometry(app_config):
    log_message('Merge CH, LI polygons')

    country_geojson_path = app_config['geodata']['swissBOUNDARIES3D_indexmap']['map_paths']['country']
    country_merged_geojson_path = app_config['geodata']['indexmap_indvidual_boundaries']['map_paths']['country_CH_LI']

    OGR2OGR_Helpers.merge_geojson_geometries(country_geojson_path, country_merged_geojson_path, override_dst=True)

    country_merged_fc = FeatureCollection.init_from_file(country_merged_geojson_path)
    if len(country_merged_fc.features) != 1:
        print(f'ERROR - expected only one feature')
        print(f'Path: {country_merged_geojson_path}')
        print(country_merged_fc.features)
        sys.exit(1)

    country_merged_geometry = country_merged_fc.features[0].geometry
    country_merged_properties = {
        'feature_id': 1001,
        'country_code': 'CH+LI',
    }
    country_merged_feature = Feature(country_merged_geometry, country_merged_properties)
    
    country_merged_massaged_fc = FeatureCollection()
    country_merged_massaged_fc.description = 'Polygon features of CH + LI'
    country_merged_massaged_fc.add_feature(country_merged_feature)
    country_merged_massaged_fc.save_to_path(country_merged_geojson_path)

    log_message(f'... saved GeoJSON to {country_merged_geojson_path}')

    log_message('... DONE merge CH, LI polygons')

if __name__ == "__main__":
    main()