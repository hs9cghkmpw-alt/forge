// GENERATED FILE — DO NOT EDIT BY HAND.
//
// `scripts/export_quality_gate_fixtures.py` が本番の
// `POST /api/v1/ai/generate` を叩いて生成する
// (Generated UI Quality Gate v2)。
//
// **手で直さないこと。** 直すべきは生成側であり、ここを直すと
// 「Backendが作る画面」と「撮影した画面」が別物になる。

/// 撮影対象の Forge Document。キーは Need の識別子。
const Map<String, Map<String, dynamic>> forgeQualityGateDocuments =
    <String, Map<String, dynamic>>{
  'analytics': <String, dynamic>{
    'version': '1.5',
    'initial_screen_id': 'generated_screen',
    'screens': <dynamic>[
      <String, dynamic>{
        'id': 'generated_screen',
        'title': '部署ごとの売上を月別に集計してグラフで比べたい',
        'state': <String, dynamic>{
          'items': <String, dynamic>{
            'type': 'checklist',
            'value': <dynamic>[],
          },
          'new_item_text': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
        },
        'body': <String, dynamic>{
          'type': 'column',
          'id': 'root_column',
          'children': <dynamic>[
            <String, dynamic>{
              'type': 'checklist',
              'id': 'list_view',
              'state_ref': 'items',
              'empty_state_text': 'まだ何もありません',
            },
            <String, dynamic>{
              'type': 'row',
              'id': 'add_row',
              'children': <dynamic>[
                <String, dynamic>{
                  'type': 'text_field',
                  'id': 'add_field',
                  'state_ref': 'new_item_text',
                  'placeholder': '追加する',
                },
                <String, dynamic>{
                  'type': 'button',
                  'id': 'add_button',
                  'label': '追加',
                  'action': <String, dynamic>{
                    'type': 'add_item',
                    'target_state_ref': 'items',
                    'source_state_ref': 'new_item_text',
                  },
                },
              ],
            },
          ],
        },
      },
    ],
    'app': <String, dynamic>{
      'title': '部署ごとの売上を月別に集計してグラフで比べたい',
    },
    'design_tokens': <String, dynamic>{
      'color_scheme': <String, dynamic>{
        'primary': '#5B7C99',
        'secondary': '#8FA8BD',
        'success': '#6B9080',
        'error': '#C1666B',
      },
      'corner_radius': <String, dynamic>{
        'small': 8,
        'medium': 12,
        'large': 16,
      },
      'spacing_scale': <String, dynamic>{
        'xs': 4,
        'sm': 8,
        'md': 16,
        'lg': 24,
        'xl': 32,
      },
    },
  },
  'finance': <String, dynamic>{
    'version': '1.12',
    'initial_screen_id': 'generated_screen',
    'screens': <dynamic>[
      <String, dynamic>{
        'id': 'generated_screen',
        'title': '毎日の収入と支出を記録して残高を見たい',
        'state': <String, dynamic>{
          'records': <String, dynamic>{
            'type': 'record_list',
            'value': <dynamic>[],
            'schema_ref': 'transaction',
          },
          'field_entry_type': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
          'field_category': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
          'field_amount': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
          'field_date': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
          'field_payment_method': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
          'selected': <String, dynamic>{
            'type': 'selected_record',
            'value': null,
          },
          'edit_field_entry_type': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
          'edit_field_category': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
          'edit_field_amount': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
          'edit_field_date': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
          'edit_field_payment_method': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
        },
        'body': <String, dynamic>{
          'type': 'tab_view',
          'id': 'root_tabs',
          'tab_titles': <dynamic>[
            '家計簿記録を追加',
            '家計簿記録一覧',
            '家計簿記録を編集',
          ],
          'style_role': 'density.normal',
          'children': <dynamic>[
            <String, dynamic>{
              'type': 'column',
              'id': 'create_tab',
              'children': <dynamic>[
                <String, dynamic>{
                  'type': 'section_header',
                  'id': 'create_section_header',
                  'style_role': 'text.headline',
                  'title': '家計簿記録を追加',
                  'subtitle': '必要な情報を入力してください',
                },
                <String, dynamic>{
                  'type': 'form',
                  'id': 'record_form',
                  'style_role': 'button.primary',
                  'submit_label': '保存',
                  'submit_action': <String, dynamic>{
                    'type': 'composite',
                    'actions': <dynamic>[
                      <String, dynamic>{
                        'type': 'add_record',
                        'target_state_ref': 'records',
                        'field_bindings': <String, dynamic>{
                          'entry_type': 'field_entry_type',
                          'category': 'field_category',
                          'amount': 'field_amount',
                          'date': 'field_date',
                          'payment_method': 'field_payment_method',
                        },
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'field_entry_type',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'field_category',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'field_amount',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'field_date',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'field_payment_method',
                      },
                    ],
                  },
                  'children': <dynamic>[
                    <String, dynamic>{
                      'type': 'choice_field',
                      'id': 'field_entry_type_input',
                      'state_ref': 'field_entry_type',
                      'label': '収支',
                      'options': <dynamic>[
                        '支出',
                        '収入',
                      ],
                    },
                    <String, dynamic>{
                      'type': 'choice_field',
                      'id': 'field_category_input',
                      'state_ref': 'field_category',
                      'label': 'カテゴリ',
                      'options': <dynamic>[
                        '食費',
                        '交通費',
                        '娯楽',
                        'その他',
                      ],
                    },
                    <String, dynamic>{
                      'type': 'text_field',
                      'id': 'field_amount_input',
                      'state_ref': 'field_amount',
                      'placeholder': '金額',
                      'validation': <String, dynamic>{
                        'rules': <dynamic>[
                          <String, dynamic>{
                            'type': 'required',
                            'message': '金額を入力してください',
                          },
                          <String, dynamic>{
                            'type': 'pattern',
                            'message': '金額は数字で入力してください',
                            'value': '^-?[0-9]+(\\.[0-9]+)?\$',
                          },
                        ],
                      },
                    },
                    <String, dynamic>{
                      'type': 'date_field',
                      'id': 'field_date_input',
                      'state_ref': 'field_date',
                      'label': '日付',
                    },
                    <String, dynamic>{
                      'type': 'text_field',
                      'id': 'field_payment_method_input',
                      'state_ref': 'field_payment_method',
                      'placeholder': '支払方法',
                    },
                  ],
                },
              ],
            },
            <String, dynamic>{
              'type': 'column',
              'id': 'list_tab',
              'children': <dynamic>[
                <String, dynamic>{
                  'type': 'metric_view',
                  'id': 'records_balance_metric',
                  'style_role': 'metric.primary',
                  'state_ref': 'records',
                  'value_field': 'amount',
                  'aggregate': 'sum',
                  'label': '残高',
                  'empty_text': 'まだ記録がありません',
                  'sign_field': 'entry_type',
                  'negative_when': '支出',
                },
                <String, dynamic>{
                  'type': 'metric_view',
                  'id': 'records_income_metric',
                  'style_role': 'finance.income',
                  'state_ref': 'records',
                  'value_field': 'amount',
                  'aggregate': 'sum',
                  'label': '収入の合計',
                  'empty_text': 'まだ記録がありません',
                  'filter_field': 'entry_type',
                  'filter_value': '収入',
                },
                <String, dynamic>{
                  'type': 'metric_view',
                  'id': 'records_expense_metric',
                  'style_role': 'finance.expense',
                  'state_ref': 'records',
                  'value_field': 'amount',
                  'aggregate': 'sum',
                  'label': '支出の合計',
                  'empty_text': 'まだ記録がありません',
                  'filter_field': 'entry_type',
                  'filter_value': '支出',
                },
                <String, dynamic>{
                  'type': 'record_list_view',
                  'id': 'records_list_view',
                  'state_ref': 'records',
                  'layout': 'card',
                  'display_fields': <dynamic>[
                    'entry_type',
                    'category',
                    'amount',
                    'date',
                    'payment_method',
                  ],
                  'empty_state_text': 'まだ家計簿記録がありません',
                  'selectable': true,
                  'selected_state_ref': 'selected',
                  'select_field_bindings': <String, dynamic>{
                    'entry_type': 'edit_field_entry_type',
                    'category': 'edit_field_category',
                    'amount': 'edit_field_amount',
                    'date': 'edit_field_date',
                    'payment_method': 'edit_field_payment_method',
                  },
                  'style_role': 'surface.card',
                },
                <String, dynamic>{
                  'type': 'bar_chart',
                  'id': 'records_bar_chart',
                  'style_role': 'card.summary',
                  'state_ref': 'records',
                  'value_field': 'amount',
                  'label_field': 'category',
                  'title': '家計簿記録の金額',
                },
              ],
            },
            <String, dynamic>{
              'type': 'column',
              'id': 'edit_tab',
              'children': <dynamic>[
                <String, dynamic>{
                  'type': 'section_header',
                  'id': 'edit_section_header',
                  'style_role': 'text.headline',
                  'title': '家計簿記録を編集',
                  'subtitle': '一覧からカードを選ぶと入力欄が埋まります',
                },
                <String, dynamic>{
                  'type': 'form',
                  'id': 'record_edit_form',
                  'submit_label': '更新',
                  'submit_action': <String, dynamic>{
                    'type': 'composite',
                    'actions': <dynamic>[
                      <String, dynamic>{
                        'type': 'update_record',
                        'target_state_ref': 'records',
                        'record_id_ref': 'selected',
                        'field_bindings': <String, dynamic>{
                          'entry_type': 'edit_field_entry_type',
                          'category': 'edit_field_category',
                          'amount': 'edit_field_amount',
                          'date': 'edit_field_date',
                          'payment_method': 'edit_field_payment_method',
                        },
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'edit_field_entry_type',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'edit_field_category',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'edit_field_amount',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'edit_field_date',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'edit_field_payment_method',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'selected',
                      },
                    ],
                  },
                  'children': <dynamic>[
                    <String, dynamic>{
                      'type': 'choice_field',
                      'id': 'edit_field_entry_type_edit_input',
                      'state_ref': 'edit_field_entry_type',
                      'label': '収支',
                      'options': <dynamic>[
                        '支出',
                        '収入',
                      ],
                    },
                    <String, dynamic>{
                      'type': 'choice_field',
                      'id': 'edit_field_category_edit_input',
                      'state_ref': 'edit_field_category',
                      'label': 'カテゴリ',
                      'options': <dynamic>[
                        '食費',
                        '交通費',
                        '娯楽',
                        'その他',
                      ],
                    },
                    <String, dynamic>{
                      'type': 'text_field',
                      'id': 'edit_field_amount_edit_input',
                      'state_ref': 'edit_field_amount',
                      'placeholder': '金額',
                      'validation': <String, dynamic>{
                        'rules': <dynamic>[
                          <String, dynamic>{
                            'type': 'required',
                            'message': '金額を入力してください',
                          },
                          <String, dynamic>{
                            'type': 'pattern',
                            'message': '金額は数字で入力してください',
                            'value': '^-?[0-9]+(\\.[0-9]+)?\$',
                          },
                        ],
                      },
                    },
                    <String, dynamic>{
                      'type': 'date_field',
                      'id': 'edit_field_date_edit_input',
                      'state_ref': 'edit_field_date',
                      'label': '日付',
                    },
                    <String, dynamic>{
                      'type': 'text_field',
                      'id': 'edit_field_payment_method_edit_input',
                      'state_ref': 'edit_field_payment_method',
                      'placeholder': '支払方法',
                    },
                  ],
                },
                <String, dynamic>{
                  'type': 'button',
                  'id': 'record_delete_button',
                  'style_role': 'button.secondary',
                  'label': '削除',
                  'action': <String, dynamic>{
                    'type': 'composite',
                    'actions': <dynamic>[
                      <String, dynamic>{
                        'type': 'delete_record',
                        'target_state_ref': 'records',
                        'record_id_ref': 'selected',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'edit_field_entry_type',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'edit_field_category',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'edit_field_amount',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'edit_field_date',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'edit_field_payment_method',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'selected',
                      },
                    ],
                  },
                },
              ],
            },
          ],
        },
      },
    ],
    'app': <String, dynamic>{
      'title': '毎日の収入と支出を記録して残高を見たい',
    },
    'record_schemas': <String, dynamic>{
      'transaction': <String, dynamic>{
        'fields': <dynamic>[
          <String, dynamic>{
            'name': 'entry_type',
            'type': 'choice',
            'label': '収支',
            'required': true,
            'options': <dynamic>[
              '支出',
              '収入',
            ],
          },
          <String, dynamic>{
            'name': 'category',
            'type': 'choice',
            'label': 'カテゴリ',
            'required': true,
            'options': <dynamic>[
              '食費',
              '交通費',
              '娯楽',
              'その他',
            ],
          },
          <String, dynamic>{
            'name': 'amount',
            'type': 'number',
            'label': '金額',
            'required': true,
          },
          <String, dynamic>{
            'name': 'date',
            'type': 'date',
            'label': '日付',
            'required': false,
          },
          <String, dynamic>{
            'name': 'payment_method',
            'type': 'string',
            'label': '支払方法',
            'required': false,
          },
        ],
      },
    },
    'design_tokens': <String, dynamic>{
      'color_scheme': <String, dynamic>{
        'primary': '#5B7C99',
        'secondary': '#8FA8BD',
        'success': '#6B9080',
        'error': '#C1666B',
      },
      'corner_radius': <String, dynamic>{
        'small': 8,
        'medium': 12,
        'large': 16,
      },
      'spacing_scale': <String, dynamic>{
        'xs': 4,
        'sm': 8,
        'md': 16,
        'lg': 24,
        'xl': 32,
      },
    },
  },
  'game': <String, dynamic>{
    'version': '1.5',
    'initial_screen_id': 'generated_screen',
    'screens': <dynamic>[
      <String, dynamic>{
        'id': 'generated_screen',
        'title': '植物を育てながら音を組み合わせるゲーム',
        'state': <String, dynamic>{
          'items': <String, dynamic>{
            'type': 'checklist',
            'value': <dynamic>[],
          },
          'new_item_text': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
        },
        'body': <String, dynamic>{
          'type': 'column',
          'id': 'root_column',
          'children': <dynamic>[
            <String, dynamic>{
              'type': 'checklist',
              'id': 'list_view',
              'state_ref': 'items',
              'empty_state_text': 'まだ何もありません',
            },
            <String, dynamic>{
              'type': 'row',
              'id': 'add_row',
              'children': <dynamic>[
                <String, dynamic>{
                  'type': 'text_field',
                  'id': 'add_field',
                  'state_ref': 'new_item_text',
                  'placeholder': '追加する',
                },
                <String, dynamic>{
                  'type': 'button',
                  'id': 'add_button',
                  'label': '追加',
                  'action': <String, dynamic>{
                    'type': 'add_item',
                    'target_state_ref': 'items',
                    'source_state_ref': 'new_item_text',
                  },
                },
              ],
            },
          ],
        },
      },
    ],
    'app': <String, dynamic>{
      'title': '植物を育てながら音を組み合わせるゲーム',
    },
    'design_tokens': <String, dynamic>{
      'color_scheme': <String, dynamic>{
        'primary': '#5B7C99',
        'secondary': '#8FA8BD',
        'success': '#6B9080',
        'error': '#C1666B',
      },
      'corner_radius': <String, dynamic>{
        'small': 8,
        'medium': 12,
        'large': 16,
      },
      'spacing_scale': <String, dynamic>{
        'xs': 4,
        'sm': 8,
        'md': 16,
        'lg': 24,
        'xl': 32,
      },
    },
  },
  'kids': <String, dynamic>{
    'version': '1.5',
    'initial_screen_id': 'generated_screen',
    'screens': <dynamic>[
      <String, dynamic>{
        'id': 'generated_screen',
        'title': '子どもが朝の支度をひとつずつチェックできるようにしたい',
        'state': <String, dynamic>{
          'items': <String, dynamic>{
            'type': 'checklist',
            'value': <dynamic>[
              <String, dynamic>{
                'id': 'item_1',
                'text': '体重測定',
                'done': false,
              },
              <String, dynamic>{
                'id': 'item_2',
                'text': '身長測定',
                'done': false,
              },
            ],
          },
          'new_item_text': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
        },
        'body': <String, dynamic>{
          'type': 'column',
          'id': 'root_column',
          'children': <dynamic>[
            <String, dynamic>{
              'type': 'checklist',
              'id': 'list_view',
              'state_ref': 'items',
              'empty_state_text': 'まだ何もありません',
            },
            <String, dynamic>{
              'type': 'row',
              'id': 'add_row',
              'children': <dynamic>[
                <String, dynamic>{
                  'type': 'text_field',
                  'id': 'add_field',
                  'state_ref': 'new_item_text',
                  'placeholder': '追加する',
                },
                <String, dynamic>{
                  'type': 'button',
                  'id': 'add_button',
                  'label': '追加',
                  'action': <String, dynamic>{
                    'type': 'add_item',
                    'target_state_ref': 'items',
                    'source_state_ref': 'new_item_text',
                  },
                },
              ],
            },
          ],
        },
      },
    ],
    'app': <String, dynamic>{
      'title': '子どもが朝の支度をひとつずつチェックできるようにしたい',
    },
    'design_tokens': <String, dynamic>{
      'color_scheme': <String, dynamic>{
        'primary': '#D68C45',
        'secondary': '#E8B37A',
        'success': '#7A9D6F',
        'error': '#C1666B',
      },
      'corner_radius': <String, dynamic>{
        'small': 10,
        'medium': 16,
        'large': 24,
      },
      'spacing_scale': <String, dynamic>{
        'xs': 4,
        'sm': 8,
        'md': 16,
        'lg': 24,
        'xl': 32,
      },
    },
  },
  'map': <String, dynamic>{
    'version': '1.12',
    'initial_screen_id': 'generated_screen',
    'screens': <dynamic>[
      <String, dynamic>{
        'id': 'generated_screen',
        'title': '釣った場所を地図に残して魚の種類',
        'state': <String, dynamic>{
          'records': <String, dynamic>{
            'type': 'record_list',
            'value': <dynamic>[],
            'schema_ref': 'fish_record',
          },
          'field_species': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
          'field_size': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
          'field_weight': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
          'field_location': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
          'field_date': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
          'selected': <String, dynamic>{
            'type': 'selected_record',
            'value': null,
          },
          'edit_field_species': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
          'edit_field_size': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
          'edit_field_weight': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
          'edit_field_location': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
          'edit_field_date': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
        },
        'body': <String, dynamic>{
          'type': 'tab_view',
          'id': 'root_tabs',
          'tab_titles': <dynamic>[
            '釣果記録を追加',
            '釣果記録一覧',
            '釣果記録を編集',
          ],
          'style_role': 'density.normal',
          'children': <dynamic>[
            <String, dynamic>{
              'type': 'column',
              'id': 'create_tab',
              'children': <dynamic>[
                <String, dynamic>{
                  'type': 'section_header',
                  'id': 'create_section_header',
                  'style_role': 'text.headline',
                  'title': '釣果記録を追加',
                  'subtitle': '必要な情報を入力してください',
                },
                <String, dynamic>{
                  'type': 'form',
                  'id': 'record_form',
                  'style_role': 'button.primary',
                  'submit_label': '保存',
                  'submit_action': <String, dynamic>{
                    'type': 'composite',
                    'actions': <dynamic>[
                      <String, dynamic>{
                        'type': 'add_record',
                        'target_state_ref': 'records',
                        'field_bindings': <String, dynamic>{
                          'species': 'field_species',
                          'size': 'field_size',
                          'weight': 'field_weight',
                          'location': 'field_location',
                          'date': 'field_date',
                        },
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'field_species',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'field_size',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'field_weight',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'field_location',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'field_date',
                      },
                    ],
                  },
                  'children': <dynamic>[
                    <String, dynamic>{
                      'type': 'text_field',
                      'id': 'field_species_input',
                      'state_ref': 'field_species',
                      'placeholder': '魚種',
                      'validation': <String, dynamic>{
                        'rules': <dynamic>[
                          <String, dynamic>{
                            'type': 'required',
                            'message': '魚種を入力してください',
                          },
                        ],
                      },
                    },
                    <String, dynamic>{
                      'type': 'text_field',
                      'id': 'field_size_input',
                      'state_ref': 'field_size',
                      'placeholder': 'サイズ(cm)',
                      'validation': <String, dynamic>{
                        'rules': <dynamic>[
                          <String, dynamic>{
                            'type': 'pattern',
                            'message': 'サイズ(cm)は数字で入力してください',
                            'value': '^-?[0-9]+(\\.[0-9]+)?\$',
                          },
                        ],
                      },
                    },
                    <String, dynamic>{
                      'type': 'text_field',
                      'id': 'field_weight_input',
                      'state_ref': 'field_weight',
                      'placeholder': '重量(g)',
                      'validation': <String, dynamic>{
                        'rules': <dynamic>[
                          <String, dynamic>{
                            'type': 'pattern',
                            'message': '重量(g)は数字で入力してください',
                            'value': '^-?[0-9]+(\\.[0-9]+)?\$',
                          },
                        ],
                      },
                    },
                    <String, dynamic>{
                      'type': 'text_field',
                      'id': 'field_location_input',
                      'state_ref': 'field_location',
                      'placeholder': '場所',
                    },
                    <String, dynamic>{
                      'type': 'date_field',
                      'id': 'field_date_input',
                      'state_ref': 'field_date',
                      'label': '日付',
                    },
                  ],
                },
              ],
            },
            <String, dynamic>{
              'type': 'column',
              'id': 'list_tab',
              'children': <dynamic>[
                <String, dynamic>{
                  'type': 'metric_view',
                  'id': 'records_hero_metric',
                  'style_role': 'metric.primary',
                  'state_ref': 'records',
                  'value_field': 'size',
                  'aggregate': 'max',
                  'label': 'サイズ(cm)の最大',
                  'empty_text': 'まだ記録がありません',
                },
                <String, dynamic>{
                  'type': 'record_list_view',
                  'id': 'records_list_view',
                  'state_ref': 'records',
                  'layout': 'card',
                  'display_fields': <dynamic>[
                    'species',
                    'size',
                    'weight',
                    'location',
                    'date',
                  ],
                  'empty_state_text': 'まだ釣果記録がありません',
                  'selectable': true,
                  'selected_state_ref': 'selected',
                  'select_field_bindings': <String, dynamic>{
                    'species': 'edit_field_species',
                    'size': 'edit_field_size',
                    'weight': 'edit_field_weight',
                    'location': 'edit_field_location',
                    'date': 'edit_field_date',
                  },
                  'style_role': 'surface.card',
                },
                <String, dynamic>{
                  'type': 'bar_chart',
                  'id': 'records_bar_chart',
                  'style_role': 'card.summary',
                  'state_ref': 'records',
                  'value_field': 'size',
                  'label_field': 'species',
                  'title': '釣果記録のサイズ(cm)',
                },
              ],
            },
            <String, dynamic>{
              'type': 'column',
              'id': 'edit_tab',
              'children': <dynamic>[
                <String, dynamic>{
                  'type': 'section_header',
                  'id': 'edit_section_header',
                  'style_role': 'text.headline',
                  'title': '釣果記録を編集',
                  'subtitle': '一覧からカードを選ぶと入力欄が埋まります',
                },
                <String, dynamic>{
                  'type': 'form',
                  'id': 'record_edit_form',
                  'submit_label': '更新',
                  'submit_action': <String, dynamic>{
                    'type': 'composite',
                    'actions': <dynamic>[
                      <String, dynamic>{
                        'type': 'update_record',
                        'target_state_ref': 'records',
                        'record_id_ref': 'selected',
                        'field_bindings': <String, dynamic>{
                          'species': 'edit_field_species',
                          'size': 'edit_field_size',
                          'weight': 'edit_field_weight',
                          'location': 'edit_field_location',
                          'date': 'edit_field_date',
                        },
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'edit_field_species',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'edit_field_size',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'edit_field_weight',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'edit_field_location',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'edit_field_date',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'selected',
                      },
                    ],
                  },
                  'children': <dynamic>[
                    <String, dynamic>{
                      'type': 'text_field',
                      'id': 'edit_field_species_edit_input',
                      'state_ref': 'edit_field_species',
                      'placeholder': '魚種',
                      'validation': <String, dynamic>{
                        'rules': <dynamic>[
                          <String, dynamic>{
                            'type': 'required',
                            'message': '魚種を入力してください',
                          },
                        ],
                      },
                    },
                    <String, dynamic>{
                      'type': 'text_field',
                      'id': 'edit_field_size_edit_input',
                      'state_ref': 'edit_field_size',
                      'placeholder': 'サイズ(cm)',
                      'validation': <String, dynamic>{
                        'rules': <dynamic>[
                          <String, dynamic>{
                            'type': 'pattern',
                            'message': 'サイズ(cm)は数字で入力してください',
                            'value': '^-?[0-9]+(\\.[0-9]+)?\$',
                          },
                        ],
                      },
                    },
                    <String, dynamic>{
                      'type': 'text_field',
                      'id': 'edit_field_weight_edit_input',
                      'state_ref': 'edit_field_weight',
                      'placeholder': '重量(g)',
                      'validation': <String, dynamic>{
                        'rules': <dynamic>[
                          <String, dynamic>{
                            'type': 'pattern',
                            'message': '重量(g)は数字で入力してください',
                            'value': '^-?[0-9]+(\\.[0-9]+)?\$',
                          },
                        ],
                      },
                    },
                    <String, dynamic>{
                      'type': 'text_field',
                      'id': 'edit_field_location_edit_input',
                      'state_ref': 'edit_field_location',
                      'placeholder': '場所',
                    },
                    <String, dynamic>{
                      'type': 'date_field',
                      'id': 'edit_field_date_edit_input',
                      'state_ref': 'edit_field_date',
                      'label': '日付',
                    },
                  ],
                },
                <String, dynamic>{
                  'type': 'button',
                  'id': 'record_delete_button',
                  'style_role': 'button.secondary',
                  'label': '削除',
                  'action': <String, dynamic>{
                    'type': 'composite',
                    'actions': <dynamic>[
                      <String, dynamic>{
                        'type': 'delete_record',
                        'target_state_ref': 'records',
                        'record_id_ref': 'selected',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'edit_field_species',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'edit_field_size',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'edit_field_weight',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'edit_field_location',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'edit_field_date',
                      },
                      <String, dynamic>{
                        'type': 'reset_state',
                        'state_ref': 'selected',
                      },
                    ],
                  },
                },
              ],
            },
          ],
        },
      },
    ],
    'app': <String, dynamic>{
      'title': '釣った場所を地図に残して魚の種類',
    },
    'record_schemas': <String, dynamic>{
      'fish_record': <String, dynamic>{
        'fields': <dynamic>[
          <String, dynamic>{
            'name': 'species',
            'type': 'string',
            'label': '魚種',
            'required': true,
          },
          <String, dynamic>{
            'name': 'size',
            'type': 'number',
            'label': 'サイズ(cm)',
            'required': false,
          },
          <String, dynamic>{
            'name': 'weight',
            'type': 'number',
            'label': '重量(g)',
            'required': false,
          },
          <String, dynamic>{
            'name': 'location',
            'type': 'string',
            'label': '場所',
            'required': false,
          },
          <String, dynamic>{
            'name': 'date',
            'type': 'date',
            'label': '日付',
            'required': false,
          },
        ],
      },
    },
    'design_tokens': <String, dynamic>{
      'color_scheme': <String, dynamic>{
        'primary': '#5C6470',
        'secondary': '#8A94A6',
        'success': '#4C9A6A',
        'error': '#B5493A',
      },
      'corner_radius': <String, dynamic>{
        'small': 6,
        'medium': 10,
        'large': 14,
      },
      'spacing_scale': <String, dynamic>{
        'xs': 4,
        'sm': 8,
        'md': 16,
        'lg': 24,
        'xl': 32,
      },
    },
  },
  'photo': <String, dynamic>{
    'version': '1.5',
    'initial_screen_id': 'generated_screen',
    'screens': <dynamic>[
      <String, dynamic>{
        'id': 'generated_screen',
        'title': '旅行の写真を日付ごとに残してメモを付けたい',
        'state': <String, dynamic>{
          'items': <String, dynamic>{
            'type': 'checklist',
            'value': <dynamic>[
              <String, dynamic>{
                'id': 'item_1',
                'text': '充電器',
                'done': false,
              },
              <String, dynamic>{
                'id': 'item_2',
                'text': '着替え',
                'done': false,
              },
              <String, dynamic>{
                'id': 'item_3',
                'text': '歯ブラシ',
                'done': false,
              },
            ],
          },
          'new_item_text': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
        },
        'body': <String, dynamic>{
          'type': 'column',
          'id': 'root_column',
          'children': <dynamic>[
            <String, dynamic>{
              'type': 'checklist',
              'id': 'list_view',
              'state_ref': 'items',
              'empty_state_text': 'まだ何もありません',
            },
            <String, dynamic>{
              'type': 'row',
              'id': 'add_row',
              'children': <dynamic>[
                <String, dynamic>{
                  'type': 'text_field',
                  'id': 'add_field',
                  'state_ref': 'new_item_text',
                  'placeholder': '追加する',
                },
                <String, dynamic>{
                  'type': 'button',
                  'id': 'add_button',
                  'label': '追加',
                  'action': <String, dynamic>{
                    'type': 'add_item',
                    'target_state_ref': 'items',
                    'source_state_ref': 'new_item_text',
                  },
                },
              ],
            },
          ],
        },
      },
    ],
    'app': <String, dynamic>{
      'title': '旅行の写真を日付ごとに残してメモを付けたい',
    },
    'design_tokens': <String, dynamic>{
      'color_scheme': <String, dynamic>{
        'primary': '#D68C45',
        'secondary': '#E8B37A',
        'success': '#7A9D6F',
        'error': '#C1666B',
      },
      'corner_radius': <String, dynamic>{
        'small': 10,
        'medium': 16,
        'large': 24,
      },
      'spacing_scale': <String, dynamic>{
        'xs': 4,
        'sm': 8,
        'md': 16,
        'lg': 24,
        'xl': 32,
      },
    },
  },
  'study': <String, dynamic>{
    'version': '1.5',
    'initial_screen_id': 'generated_screen',
    'screens': <dynamic>[
      <String, dynamic>{
        'id': 'generated_screen',
        'title': '英単語を出題して、正解率の推移を見たい',
        'state': <String, dynamic>{
          'items': <String, dynamic>{
            'type': 'checklist',
            'value': <dynamic>[],
          },
          'new_item_text': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
        },
        'body': <String, dynamic>{
          'type': 'column',
          'id': 'root_column',
          'children': <dynamic>[
            <String, dynamic>{
              'type': 'checklist',
              'id': 'list_view',
              'state_ref': 'items',
              'empty_state_text': 'まだ何もありません',
            },
            <String, dynamic>{
              'type': 'row',
              'id': 'add_row',
              'children': <dynamic>[
                <String, dynamic>{
                  'type': 'text_field',
                  'id': 'add_field',
                  'state_ref': 'new_item_text',
                  'placeholder': '追加する',
                },
                <String, dynamic>{
                  'type': 'button',
                  'id': 'add_button',
                  'label': '追加',
                  'action': <String, dynamic>{
                    'type': 'add_item',
                    'target_state_ref': 'items',
                    'source_state_ref': 'new_item_text',
                  },
                },
              ],
            },
          ],
        },
      },
    ],
    'app': <String, dynamic>{
      'title': '英単語を出題して、正解率の推移を見たい',
    },
    'design_tokens': <String, dynamic>{
      'color_scheme': <String, dynamic>{
        'primary': '#5B7C99',
        'secondary': '#8FA8BD',
        'success': '#6B9080',
        'error': '#C1666B',
      },
      'corner_radius': <String, dynamic>{
        'small': 8,
        'medium': 12,
        'large': 16,
      },
      'spacing_scale': <String, dynamic>{
        'xs': 4,
        'sm': 8,
        'md': 16,
        'lg': 24,
        'xl': 32,
      },
    },
  },
  'worklog': <String, dynamic>{
    'version': '1.5',
    'initial_screen_id': 'generated_screen',
    'screens': <dynamic>[
      <String, dynamic>{
        'id': 'generated_screen',
        'title': '今日やる作業を登録して、終わったものを消していきたい',
        'state': <String, dynamic>{
          'items': <String, dynamic>{
            'type': 'checklist',
            'value': <dynamic>[
              <String, dynamic>{
                'id': 'item_1',
                'text': '買い物に行く',
                'done': false,
              },
              <String, dynamic>{
                'id': 'item_2',
                'text': '部屋を掃除する',
                'done': false,
              },
              <String, dynamic>{
                'id': 'item_3',
                'text': 'メールを返信する',
                'done': false,
              },
            ],
          },
          'new_item_text': <String, dynamic>{
            'type': 'string',
            'value': '',
          },
        },
        'body': <String, dynamic>{
          'type': 'column',
          'id': 'root_column',
          'children': <dynamic>[
            <String, dynamic>{
              'type': 'checklist',
              'id': 'list_view',
              'state_ref': 'items',
              'empty_state_text': 'まだ何もありません',
            },
            <String, dynamic>{
              'type': 'row',
              'id': 'add_row',
              'children': <dynamic>[
                <String, dynamic>{
                  'type': 'text_field',
                  'id': 'add_field',
                  'state_ref': 'new_item_text',
                  'placeholder': '追加する',
                },
                <String, dynamic>{
                  'type': 'button',
                  'id': 'add_button',
                  'label': '追加',
                  'action': <String, dynamic>{
                    'type': 'add_item',
                    'target_state_ref': 'items',
                    'source_state_ref': 'new_item_text',
                  },
                },
              ],
            },
          ],
        },
      },
    ],
    'app': <String, dynamic>{
      'title': '今日やる作業を登録して、終わったものを消していきたい',
    },
    'design_tokens': <String, dynamic>{
      'color_scheme': <String, dynamic>{
        'primary': '#6366F1',
        'secondary': '#EC4899',
        'success': '#10B981',
        'error': '#EF4444',
      },
      'corner_radius': <String, dynamic>{
        'small': 12,
        'medium': 18,
        'large': 28,
      },
      'spacing_scale': <String, dynamic>{
        'xs': 4,
        'sm': 8,
        'md': 16,
        'lg': 24,
        'xl': 32,
      },
    },
  },
};
