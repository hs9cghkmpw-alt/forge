import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';
import 'package:forge_app/json_ui/widget_registry/widget_registry_v1_16.dart';

void main() {
  group('Forge v1.16 map_view', () {
    test('parser preserves geographic binding contract', () {
      final node = ForgeWidgetNode.fromJson({
        'type': 'map_view',
        'id': 'map',
        'state_ref': 'records',
        'latitude_field': 'latitude',
        'longitude_field': 'longitude',
        'label_field': 'name',
        'title': 'Locations',
        'initial_zoom': 9,
        'height': 280,
      }, r'$/body');

      expect(node, isA<ForgeMapViewWidgetNode>());
      final map = node as ForgeMapViewWidgetNode;
      expect(map.stateRef, 'records');
      expect(map.latitudeField, 'latitude');
      expect(map.longitudeField, 'longitude');
      expect(map.labelField, 'name');
      expect(map.initialZoom, 9);
      expect(map.height, 280);
    });

    test('coordinate extraction keeps valid points and rejects invalid coordinates', () {
      const records = [
        ForgeRecordItem(
          id: 'valid',
          fields: {'latitude': 43.0618, 'longitude': 141.3545, 'name': 'Sapporo'},
        ),
        ForgeRecordItem(
          id: 'out_of_range',
          fields: {'latitude': 120, 'longitude': 141.0, 'name': 'invalid'},
        ),
        ForgeRecordItem(
          id: 'not_numeric',
          fields: {'latitude': '43.0', 'longitude': 141.0, 'name': 'invalid'},
        ),
      ];

      final points = extractForgeMapPoints(
        records,
        latitudeField: 'latitude',
        longitudeField: 'longitude',
        labelField: 'name',
      );

      expect(points, hasLength(1));
      expect(points.single.latitude, closeTo(43.0618, 0.000001));
      expect(points.single.longitude, closeTo(141.3545, 0.000001));
      expect(points.single.label, 'Sapporo');
    });

    test('missing label falls back to stable record id', () {
      const records = [
        ForgeRecordItem(id: 'p1', fields: {'latitude': 35.0, 'longitude': 139.0}),
      ];
      final points = extractForgeMapPoints(
        records,
        latitudeField: 'latitude',
        longitudeField: 'longitude',
        labelField: 'name',
      );
      expect(points.single.label, 'p1');
    });
  });
}
