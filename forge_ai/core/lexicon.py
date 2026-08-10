"""共有語彙(Shared Lexicon)。

`FORGE_v0.2_COMPLETE_IMPLEMENTATION_DIRECTIVE.md` PART B 7.1節
(Ambiguity Detectionの8分類完成)への対応で新設した。

**背景**: 以前は`understanding/intent_recognizer.py`だけが日本語キーワード
→概念/操作名の対応表を持っていた。`input_processing/ambiguity_detector.py`
(missing_domain・多重Template候補等の検出)にも同じ語彙が必要になったが、
Blueprint Task5.2「input_processing/・understanding/・planning/・critic/・
confirmation/の同階層モジュール間の直接import禁止」により、
`ambiguity_detector.py`が`understanding/intent_recognizer.py`を直接
importすることは許されない。

そのため、この語彙を依存方向の下位層である`core/`(Task5.1の依存図で
`input_processing/`・`understanding/`の両方が依存してよい層)へ移動した。
`intent_recognizer.py`もここを参照するよう更新し、辞書の二重管理を避けた。

この辞書は`domain_model.py`の各Domainの`typical_concepts`/
`typical_actions`(英語識別子)と対応させてある。
"""

from __future__ import annotations

# (日本語キーワード, 対応する概念名) — domain_model.pyのtypical_concepts.nameと対応させる。
CONCEPT_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("買い物", "item"), ("品物", "item"), ("商品", "item"), ("買い物リスト", "item"),
    ("値段", "price"), ("価格", "price"),
    ("個数", "quantity"), ("数量", "quantity"),
    ("店", "store"), ("スーパー", "store"),
    ("患者", "patient"), ("診察", "appointment"), ("症状", "symptom"), ("薬", "medication"),
    ("出欠", "status"), ("出席", "status"), ("会員", "member"),
    ("日記", "entry"), ("気分", "mood"),
    ("在庫", "stock"), ("保管場所", "location"), ("置き場", "location"), ("閾値", "threshold"),
    ("タスク", "task"), ("作業", "task"), ("業務", "task"), ("期限", "deadline"), ("優先度", "priority"),
    ("アンケート", "question"), ("質問", "question"), ("回答", "answer"), ("回答者", "respondent"),
    ("予定", "event"), ("スケジュール", "event"), ("時間", "time"), ("参加者", "participant"),
    # FORGE_v0.2_修正指示.md P2 11章対応 + FORGE v0.3 Task1で拡充:
    # 家計簿(household_budget)。
    ("家計簿", "transaction"), ("収入", "transaction"), ("支出", "transaction"), ("出費", "transaction"),
    ("費目", "category"), ("金額", "amount"), ("予算", "budget_limit"),
    ("食費", "category"), ("交通費", "category"), ("固定費", "category"),
    # FORGE_v0.2_修正指示.md P2 11章対応: 成長記録(child_growth)。
    ("成長記録", "child"), ("子ども", "child"), ("こども", "child"), ("赤ちゃん", "child"),
    ("身長", "measurement"), ("体重", "measurement"), ("発達", "milestone"), ("成長", "milestone"),
    # 既知の制限: "写真"->"photo"は意図的にマッピングしていない。実装時に
    # 検証した結果、「写真」を含む入力(例:「写真と気分を記録できる日記」)
    # では、Diary Domainが選ばれた場合にIntent.required_conceptsへ"photo"
    # が含まれてしまい、Diary DomainのWorld Modelには"photo"という概念が
    # 無いため、Requirement Extractionが「'photo'のデータを保持できる
    # こと」という必須要件を生成しながらApplicationPlanへ絶対に反映
    # できない(=Design Criticが永久にrelease_ready=Falseのままになる)
    # という、既存Requirement Extraction/Planningの構造的な問題を誘発
    # することが判明した(既存の複合Golden Test `02_photo_mood_diary`で
    # 検出)。この根本原因(Intent.required_conceptsが、選ばれたDomainの
    # World Modelでサポートされない概念を含みうる)自体の修正は、今回の
    # セッションのスコープ(Ambiguity Detection・Lexicon拡充)を超える
    # ため、対症療法として"写真"のキーワード登録を見送った。child_growth
    # Domain自体はphotoという概念を持ったまま(将来の拡張点として維持)。
    #
    # FORGE v0.3 Task1対応: 釣果記録(fishing_log)。以前はDiaryへ
    # 吸収されていた分野(「釣った魚を記録する」等)を独立させる。
    ("釣り", "catch"), ("釣果", "catch"), ("釣った魚", "catch"),
    ("魚", "species"), ("魚種", "species"),
    ("カレイ", "species"), ("サケ", "species"), ("アジ", "species"),
    ("イワシ", "species"), ("ヒラメ", "species"),
    ("場所", "location"), ("サイズ", "size"), ("大きさ", "size"), ("重量", "weight"),
    # FORGE v0.3 Task1対応: 習慣記録(habit_tracking)。
    #
    # 既知の制限: "毎日"->"habit"は当初追加したが、実装時の検証で
    # 「毎日の気分を記録したい」(本来はDiary domain)のような、
    # habit_trackingと無関係な文でも"habit"概念が誤って一致し、
    # Diary DomainのWorld Modelがサポートしない"habit"という必須
    # データ要件を生成してしまう(=Design Criticが永久にrelease_
    # ready=Falseになる)、既存の"写真"問題(`lexicon.py`の別コメント
    # 参照)と同種の構造的な問題を引き起こすことが判明した。「毎日」は
    # 日常会話で極めて頻出する語であり、習慣記録に固有ではないため、
    # マッピングを見送った。
    ("習慣", "habit"), ("ルーティン", "habit"),
    ("健康", "category"), ("運動", "habit"), ("筋トレ", "habit"), ("散歩", "habit"), ("睡眠", "habit"),
    # FORGE v0.3 Task1対応: 学習記録(study)。
    ("勉強", "subject"), ("学習", "subject"), ("英語", "subject"),
    ("資格", "certification"), ("読書", "material"),
    # FORGE v0.3 Task1対応: 旅行記録(travel)。
    ("旅行", "destination"), ("ホテル", "accommodation"), ("観光", "itinerary"),
    ("温泉", "destination"), ("飛行機", "itinerary"), ("旅程", "itinerary"),
)

# (日本語キーワード, 対応する操作名) — domain_model.pyのtypical_actionsと対応させる。
# 注記: "管理"・"作りたい"・"作る"のような、複数Domainで共通して使われる
# 汎用的な動詞は、あえてここへ入れていない(実際にテストした結果、
# 例えば"管理"を特定のActionへ対応させると、Domain Classificationの
# スコアリング時に無関係なDomainへ誤って加点してしまい、本来明確な
# はずの判定が同点になってしまう問題を発見したため)。Domain判定は
# 主にConcept一致に委ね、Actionは明確に対応が取れるものだけに限定する。
ACTION_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("追加", "add_item"),
    ("記録", "add_entry"),
    ("削除", "remove_item"), ("消す", "remove_item"),
    ("完了", "complete_task"),
    ("編集", "edit_entry"),
)

# Ambiguity Detection専用: Domain Classificationの得点には使わない
# (上記ACTION_KEYWORDSに"管理"等を入れない理由と同じ)、あくまで
# 「何らかの操作意図が文中にあるか」を判定するための、より広い動詞集合。
# missing_data判定(操作意図はあるが対象データが不明)専用に使う。
GENERIC_ACTION_HINTS: tuple[str, ...] = (
    "管理", "作", "記録", "整理", "追跡", "登録", "追加", "編集", "削除", "確認", "共有",
)

# Actorを示唆する語(明示的な利用者・関係者への言及)。M006 4.2節「LOW:
# Actorが明示されていないが『利用者本人』と仮定して問題ない」の判定に使う。
ACTOR_HINTS: tuple[str, ...] = (
    "私", "自分", "家族", "みんな", "全員", "メンバー", "会員", "スタッフ", "従業員",
    "顧客", "患者", "子ども", "こども", "利用者", "参加者", "回答者", "管理者", "担当者",
)

# conflicting_requirements検出用の、明確に矛盾しうる語のペア。
# 部分一致による簡易ヒューリスティックであり、完全ではない(既知の制限)。
CONTRADICTION_PAIRS: tuple[tuple[str, str], ...] = (
    ("公開", "非公開"),
    ("共有したい", "自分だけ"),
    ("シンプル", "詳細"),
    ("シンプル", "高度"),
    ("誰でも", "限定"),
    ("無料", "有料"),
)
