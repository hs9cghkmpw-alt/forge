/// Forge Language v1.16 geographic map primitive.
///
/// `map_view` renders real geographic coordinates from a record_list using
/// OpenStreetMap tiles. It does not geocode free-form place names; geocoding is
/// a separate capability and must not be silently substituted.
library;

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../renderer/forge_runtime_state.dart';
import '../schema/forge_document.dart';
import 'widget_registry_core.dart';

void registerV1_16Widgets(ForgeWidgetRegistry registry) {
  registry.register('map_view', _buildMapView);
}

Widget _buildMapView(
  BuildContext context,
  ForgeWidgetNode node,
  ForgeRuntimeState state,
  Widget Function(ForgeWidgetNode) build,
) {
  final n = node as ForgeMapViewWidgetNode;
  return AnimatedBuilder(
    animation: state,
    builder: (context, _) {
      final points = extractForgeMapPoints(
        state.getRecordList(n.stateRef),
        latitudeField: n.latitudeField,
        longitudeField: n.longitudeField,
        labelField: n.labelField,
      );
      if (points.isEmpty) {
        return Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Row(
              children: [
                const Icon(Icons.map_outlined),
                const SizedBox(width: 12),
                Expanded(child: Text(n.emptyText)),
              ],
            ),
          ),
        );
      }

      final first = points.first;
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          if (n.title != null && n.title!.isNotEmpty) ...[
            Text(n.title!, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
          ],
          ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: SizedBox(
              height: n.height,
              child: Stack(
                children: [
                  FlutterMap(
                    options: MapOptions(
                      initialCenter: LatLng(first.latitude, first.longitude),
                      initialZoom: n.initialZoom,
                    ),
                    children: [
                      TileLayer(
                        urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                        userAgentPackageName: 'forge_app',
                      ),
                      MarkerLayer(
                        markers: [
                          for (final point in points)
                            Marker(
                              point: LatLng(point.latitude, point.longitude),
                              width: 44,
                              height: 44,
                              child: Tooltip(
                                message: point.label,
                                child: const Icon(Icons.location_on, size: 36),
                              ),
                            ),
                        ],
                      ),
                    ],
                  ),
                  Positioned(
                    right: 6,
                    bottom: 4,
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        color: Theme.of(context).colorScheme.surface.withValues(alpha: 0.88),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: const Padding(
                        padding: EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                        child: Text('© OpenStreetMap contributors', style: TextStyle(fontSize: 9)),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      );
    },
  );
}

class ForgeMapPoint {
  final double latitude;
  final double longitude;
  final String label;

  const ForgeMapPoint({required this.latitude, required this.longitude, required this.label});
}

List<ForgeMapPoint> extractForgeMapPoints(
  List<ForgeRecordItem> records, {
  required String latitudeField,
  required String longitudeField,
  String? labelField,
}) {
  final result = <ForgeMapPoint>[];
  for (final record in records) {
    final latitudeRaw = record.fields[latitudeField];
    final longitudeRaw = record.fields[longitudeField];
    if (latitudeRaw is! num || longitudeRaw is! num) continue;
    final latitude = latitudeRaw.toDouble();
    final longitude = longitudeRaw.toDouble();
    if (!latitude.isFinite || !longitude.isFinite) continue;
    if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) continue;
    final labelRaw = labelField == null ? null : record.fields[labelField];
    result.add(ForgeMapPoint(
      latitude: latitude,
      longitude: longitude,
      label: labelRaw is String && labelRaw.trim().isNotEmpty ? labelRaw : record.id,
    ));
  }
  return result;
}
