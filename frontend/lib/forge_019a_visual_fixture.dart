// GENERATED FILE — DO NOT EDIT BY HAND.
//
// `scripts/export_revision_visual_fixture.py` が生成する
// (FORGE-019A §7)。
//
// After は**本番の RevisionService が実際に返した文書**である。
// 手で書くと、Backendが作るAfterと絵のAfterが別々のSource of
// Truthになり、実装を直しても絵が変わらない。
//
// intent            : 残高をもっと目立たせて
// revision_mode     : local_semantic_patch
// semantic_operation: select_primary_metric
// validator_passed  : true
// critic_passed     : true

/// 撮影シナリオの Before（唯一の手書き入力）。
Map<String, dynamic> forge019aBeforeDocument() => <String, dynamic>{
  'version': '1.12',
  'app': <String, dynamic>{
    'title': 'わたしの家計',
  },
  'initial_screen_id': 'home',
  'record_schemas': <String, dynamic>{
    'transaction': <String, dynamic>{
      'fields': <dynamic>[
        <String, dynamic>{
          'name': 'name',
          'type': 'string',
          'label': '項目',
          'required': true,
        },
        <String, dynamic>{
          'name': 'category',
          'type': 'string',
          'label': '分類',
          'required': true,
        },
        <String, dynamic>{
          'name': 'amount',
          'type': 'number',
          'label': '金額',
          'required': true,
        },
      ],
    },
  },
  'screens': <dynamic>[
    <String, dynamic>{
      'id': 'home',
      'title': '今月の家計',
      'state': <String, dynamic>{
        'records': <String, dynamic>{
          'type': 'record_list',
          'schema_ref': 'transaction',
          'value': <dynamic>[
            <String, dynamic>{
              'id': 'salary',
              'fields': <String, dynamic>{
                'name': '給与',
                'category': '収入',
                'amount': 320000,
              },
            },
            <String, dynamic>{
              'id': 'rent',
              'fields': <String, dynamic>{
                'name': '家賃',
                'category': '支出',
                'amount': 85000,
              },
            },
            <String, dynamic>{
              'id': 'food',
              'fields': <String, dynamic>{
                'name': '食費',
                'category': '支出',
                'amount': 42000,
              },
            },
          ],
        },
      },
      'body': <String, dynamic>{
        'type': 'column',
        'id': 'root',
        'children': <dynamic>[
          <String, dynamic>{
            'type': 'section_header',
            'id': 'summary_header',
            'title': '今月のサマリー',
            'style_role': 'text.headline',
          },
          <String, dynamic>{
            'type': 'metric_view',
            'id': 'income',
            'label': '収入',
            'state_ref': 'records',
            'value_field': 'amount',
            'aggregate': 'sum',
            'filter_field': 'category',
            'filter_value': '収入',
            'unit': '円',
            'style_role': 'metric.primary',
          },
          <String, dynamic>{
            'type': 'metric_view',
            'id': 'balance',
            'label': '残高',
            'state_ref': 'records',
            'value_field': 'amount',
            'aggregate': 'sum',
            'sign_field': 'category',
            'negative_when': '支出',
            'unit': '円',
            'style_role': 'metric.secondary',
          },
          <String, dynamic>{
            'type': 'metric_view',
            'id': 'expense',
            'label': '支出',
            'state_ref': 'records',
            'value_field': 'amount',
            'aggregate': 'sum',
            'filter_field': 'category',
            'filter_value': '支出',
            'unit': '円',
            'style_role': 'finance.expense',
          },
          <String, dynamic>{
            'type': 'section_header',
            'id': 'list_header',
            'title': '最近の取引',
            'style_role': 'text.headline',
          },
          <String, dynamic>{
            'type': 'text',
            'id': 'transaction_1',
            'value': '家賃　−85,000円',
          },
          <String, dynamic>{
            'type': 'text',
            'id': 'transaction_2',
            'value': '食費　−42,000円',
          },
        ],
      },
    },
  ],
};

/// 本番の RevisionService が返した After。
Map<String, dynamic> forge019aAfterDocument() => <String, dynamic>{
  'version': '1.12',
  'app': <String, dynamic>{
    'title': 'わたしの家計',
  },
  'initial_screen_id': 'home',
  'record_schemas': <String, dynamic>{
    'transaction': <String, dynamic>{
      'fields': <dynamic>[
        <String, dynamic>{
          'name': 'name',
          'type': 'string',
          'label': '項目',
          'required': true,
        },
        <String, dynamic>{
          'name': 'category',
          'type': 'string',
          'label': '分類',
          'required': true,
        },
        <String, dynamic>{
          'name': 'amount',
          'type': 'number',
          'label': '金額',
          'required': true,
        },
      ],
    },
  },
  'screens': <dynamic>[
    <String, dynamic>{
      'id': 'home',
      'title': '今月の家計',
      'state': <String, dynamic>{
        'records': <String, dynamic>{
          'type': 'record_list',
          'schema_ref': 'transaction',
          'value': <dynamic>[
            <String, dynamic>{
              'id': 'salary',
              'fields': <String, dynamic>{
                'name': '給与',
                'category': '収入',
                'amount': 320000,
              },
            },
            <String, dynamic>{
              'id': 'rent',
              'fields': <String, dynamic>{
                'name': '家賃',
                'category': '支出',
                'amount': 85000,
              },
            },
            <String, dynamic>{
              'id': 'food',
              'fields': <String, dynamic>{
                'name': '食費',
                'category': '支出',
                'amount': 42000,
              },
            },
          ],
        },
      },
      'body': <String, dynamic>{
        'type': 'column',
        'id': 'root',
        'children': <dynamic>[
          <String, dynamic>{
            'type': 'section_header',
            'id': 'summary_header',
            'title': '今月のサマリー',
            'style_role': 'text.headline',
          },
          <String, dynamic>{
            'type': 'metric_view',
            'id': 'income',
            'label': '収入',
            'state_ref': 'records',
            'value_field': 'amount',
            'aggregate': 'sum',
            'filter_field': 'category',
            'filter_value': '収入',
            'unit': '円',
            'style_role': 'finance.income',
          },
          <String, dynamic>{
            'type': 'metric_view',
            'id': 'balance',
            'label': '残高',
            'state_ref': 'records',
            'value_field': 'amount',
            'aggregate': 'sum',
            'sign_field': 'category',
            'negative_when': '支出',
            'unit': '円',
            'style_role': 'metric.primary',
          },
          <String, dynamic>{
            'type': 'metric_view',
            'id': 'expense',
            'label': '支出',
            'state_ref': 'records',
            'value_field': 'amount',
            'aggregate': 'sum',
            'filter_field': 'category',
            'filter_value': '支出',
            'unit': '円',
            'style_role': 'finance.expense',
          },
          <String, dynamic>{
            'type': 'section_header',
            'id': 'list_header',
            'title': '最近の取引',
            'style_role': 'text.headline',
          },
          <String, dynamic>{
            'type': 'text',
            'id': 'transaction_1',
            'value': '家賃　−85,000円',
          },
          <String, dynamic>{
            'type': 'text',
            'id': 'transaction_2',
            'value': '食費　−42,000円',
          },
        ],
      },
    },
  ],
};

/// この絵がどの変更のものかを示す系譜。
Map<String, dynamic> forge019aProvenance() => <String, dynamic>{
  'task': 'FORGE-019A',
  'intent': '残高をもっと目立たせて',
  'revision_mode': 'local_semantic_patch',
  'semantic_operation': 'select_primary_metric',
  'semantic_target': <String, dynamic>{
    'screen_id': 'home',
    'widget_id': 'balance',
    'semantic_identity': 'balance',
  },
  'validator_passed': true,
  'critic_passed': true,
  'patch_mode': 'local_semantic_patch',
  'forge_language_version': '1.12',
};
