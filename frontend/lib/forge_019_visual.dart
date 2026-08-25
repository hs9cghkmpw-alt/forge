import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/theme/forge_theme.dart';
import 'shared_widgets/generated_app_host_shell.dart';

void main() => runApp(const ProviderScope(child: Forge019VisualApp()));

class Forge019VisualApp extends StatelessWidget {
  const Forge019VisualApp({super.key});

  @override
  Widget build(BuildContext context) {
    final after = Uri.base.queryParameters['state'] == 'after';
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ForgeTheme.theme,
      home: Scaffold(body: SafeArea(child: GeneratedAppHostShell(
        forgeDocument: forge019FinanceDocument(after: after),
      ))),
    );
  }
}

Map<String, dynamic> forge019FinanceDocument({required bool after}) => {
  'version': '1.12',
  'app': {'title': 'わたしの家計'},
  'initial_screen_id': 'home',
  'record_schemas': {
    'transaction': {'fields': [
      {'name': 'name', 'type': 'string', 'label': '項目', 'required': true},
      {'name': 'category', 'type': 'string', 'label': '分類', 'required': true},
      {'name': 'amount', 'type': 'number', 'label': '金額', 'required': true},
    ]},
  },
  'screens': [{
    'id': 'home', 'title': '今月の家計',
    'state': {'records': {'type': 'record_list', 'schema_ref': 'transaction', 'value': [
      {'id': 'salary', 'fields': {'name': '給与', 'category': '収入', 'amount': 320000}},
      {'id': 'rent', 'fields': {'name': '家賃', 'category': '支出', 'amount': 85000}},
      {'id': 'food', 'fields': {'name': '食費', 'category': '支出', 'amount': 42000}},
    ]}},
    'body': {'type': 'column', 'id': 'root', 'children': [
      {'type': 'section_header', 'id': 'summary_header', 'title': '今月のサマリー', 'style_role': 'text.headline'},
      {'type': 'metric_view', 'id': 'income', 'label': '収入', 'state_ref': 'records',
       'value_field': 'amount', 'aggregate': 'sum', 'filter_field': 'category', 'filter_value': '収入',
       'unit': '円', 'style_role': after ? 'finance.income' : 'metric.primary'},
      {'type': 'metric_view', 'id': 'balance', 'label': '残高', 'state_ref': 'records',
       'value_field': 'amount', 'aggregate': 'sum', 'negative_when': '支出',
       'unit': '円', 'style_role': after ? 'metric.primary' : 'metric.secondary'},
      {'type': 'metric_view', 'id': 'expense', 'label': '支出', 'state_ref': 'records',
       'value_field': 'amount', 'aggregate': 'sum', 'filter_field': 'category', 'filter_value': '支出',
       'unit': '円', 'style_role': 'finance.expense'},
      {'type': 'section_header', 'id': 'list_header', 'title': '最近の取引', 'style_role': 'text.headline'},
      {'type': 'text', 'id': 'transaction_1', 'value': '家賃　−85,000円'},
      {'type': 'text', 'id': 'transaction_2', 'value': '食費　−42,000円'},
    ]},
  }],
};
