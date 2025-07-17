# 本番公開時チェックリスト（Patreon認証対応）

## 1. 本番用Patreonアプリの新規作成
- Patreon Developers Portalで新しいクライアント（アプリ）を作成
- アプリ名、アイコン、説明、Privacy Policy URL、Terms of Service URLを入力

## 2. 本番ドメインのRedirect URIを登録
- 例: https://yourdomain.com/patreon_login/patreon/authorized
- 必要に応じてサブドメインやwww有無も登録

## 3. Client ID / Client Secretの取得
- 新しい本番用アプリのClient IDとClient Secretを取得

## 4. .envファイルの更新（本番サーバー上で）
- 下記を本番用の値に書き換え
  PATREON_CLIENT_ID=本番用のClient ID
  PATREON_CLIENT_SECRET=本番用のClient Secret
- 必要なら他のAPIキーやDB接続情報も本番用に

## 5. OAUTHLIB_INSECURE_TRANSPORTの削除
- 本番では必ずHTTPSを使うので、.envや環境変数からOAUTHLIB_INSECURE_TRANSPORTを削除または設定しない

## 6. 本番サーバーをHTTPSで運用
- サーバー証明書（Let’s Encrypt等）でHTTPS化
- Flask本体ではなく、nginxやApacheなどのリバースプロキシでHTTPS終端するのが一般的

## 7. Patreonアプリの「公開」状態の確認
- 「(test)」表記が消えていることを確認
- 必要ならPatreonサポートに「公開申請」を依頼

## 8. 本番環境での動作確認
- 本番ドメインでPatreonログインが正常に動作するかテスト
- 必要に応じてGoogleログインや通常ログインもテスト

## 9. ユーザーDBのマイグレーション
- 本番DBにauth_providerやis_patreonカラムがなければ、マイグレーション（alembic等）を実施

---

このリストを本番公開時に順番に実施すればOKです！ 