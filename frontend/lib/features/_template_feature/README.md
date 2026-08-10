# _template_feature/

新機能を追加する際のひな形。実装しないこと（コピー専用）。

使い方:
1. このフォルダごと `features/<新機能名>/` にコピー
2. `domain/entities` → `domain/repositories`(interface) → `domain/usecases` の順に定義
3. `data/models` → `data/datasources` → `data/repositories`(実装) を実装
4. `presentation/providers` でRiverpodにより domain の usecase を束縛
5. `presentation/screens` / `widgets` でUIを組む
