import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../network/dio_client.dart';

/// アプリ全体で共有する単一のDioインスタンス。
/// riverpod_generator(コード生成)は使わず、手書きのProviderにしている
/// (理由: DECISIONS.md — freezedを見送った理由と同じく、build_runnerを
/// 必須にせず縦の一本を最短で通すため)。
final dioClientProvider = Provider<Dio>((ref) => createForgeDioClient());
