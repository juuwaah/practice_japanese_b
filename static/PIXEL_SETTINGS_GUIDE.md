# ピクセル度合い調整ガイド - Pixel Intensity Adjustment Guide

## 簡単な調整方法 - Easy Adjustment Method

`style-retro.css` の `:root` セクション（68-74行目）で、以下の6つの変数を変更するだけでピクセル度合いを調整できます：

```css
/* 現在の設定 - Current Active Settings */
--current-font-family: var(--pixel-font-bestten);       /* フォント選択 */
--current-font-size: var(--pixel-font-size-small);
--current-letter-spacing: var(--pixel-letter-spacing-normal);
--current-line-height: var(--pixel-line-height-normal);
--current-text-shadow: var(--pixel-shadow-normal);
--current-scale: var(--pixel-scale-normal);
```

## 🎌 日本語ピクセルフォント選択 - Japanese Pixel Font Selection

### フォント変更方法
```css
/* BestTen - CRTモニター風 */
--current-font-family: var(--pixel-font-bestten);

/* NostalgicDot - ドット絵風 */
--current-font-family: var(--pixel-font-nostalgic);

/* フォールバック - システムフォント */
--current-font-family: var(--pixel-font-fallback);
```

## 利用可能な設定値 - Available Settings

### 1. フォントサイズ (Font Size)
```css
--current-font-size: var(--pixel-font-size-tiny);    /* 8px - 極小・最もピクセル感 */
--current-font-size: var(--pixel-font-size-small);   /* 9px - 小（現在の設定） */
--current-font-size: var(--pixel-font-size-medium);  /* 10px - 中 */
--current-font-size: var(--pixel-font-size-large);   /* 11px - 大・ピクセル感少 */
```

### 2. 文字間隔 (Letter Spacing)
```css
--current-letter-spacing: var(--pixel-letter-spacing-tight);   /* 0.2px - 密集・クリスプ */
--current-letter-spacing: var(--pixel-letter-spacing-normal);  /* 0.5px - 標準（現在） */
--current-letter-spacing: var(--pixel-letter-spacing-loose);   /* 0.8px - 疎・レトロ感強 */
--current-letter-spacing: var(--pixel-letter-spacing-wide);    /* 1.2px - 広い・極レトロ */
```

### 3. 行間 (Line Height)
```css
--current-line-height: var(--pixel-line-height-compact);  /* 1.0 - コンパクト・密度高 */
--current-line-height: var(--pixel-line-height-normal);   /* 1.1 - 標準（現在） */
--current-line-height: var(--pixel-line-height-relaxed);  /* 1.2 - リラックス・読みやすい */
```

### 4. テキストシャドウ (Text Shadow)
```css
--current-text-shadow: var(--pixel-shadow-none);    /* なし - クリーン */
--current-text-shadow: var(--pixel-shadow-light);   /* 軽い - 0.5px */
--current-text-shadow: var(--pixel-shadow-normal);  /* 標準 - 1px（現在） */
--current-text-shadow: var(--pixel-shadow-heavy);   /* 重い - 1.5px・立体感強 */
```

### 5. スケール (Scale)
```css
--current-scale: var(--pixel-scale-tiny);    /* 0.9 - 縮小・密度高 */
--current-scale: var(--pixel-scale-normal);  /* 1.0 - 標準（現在） */
--current-scale: var(--pixel-scale-large);   /* 1.1 - 拡大・見やすい */
--current-scale: var(--pixel-scale-huge);    /* 1.2 - 大拡大・迫力 */
```

## おすすめ組み合わせ - Recommended Combinations

### 🔥 超ピクセル感（Ultra Pixelated）
```css
--current-font-size: var(--pixel-font-size-tiny);
--current-letter-spacing: var(--pixel-letter-spacing-wide);
--current-line-height: var(--pixel-line-height-compact);
--current-text-shadow: var(--pixel-shadow-heavy);
--current-scale: var(--pixel-scale-tiny);
```

### 💎 バランス良好（Balanced Retro）
```css
--current-font-size: var(--pixel-font-size-small);
--current-letter-spacing: var(--pixel-letter-spacing-normal);
--current-line-height: var(--pixel-line-height-normal);
--current-text-shadow: var(--pixel-shadow-normal);
--current-scale: var(--pixel-scale-normal);
```

### 📖 読みやすさ重視（Readable Retro）
```css
--current-font-size: var(--pixel-font-size-medium);
--current-letter-spacing: var(--pixel-letter-spacing-tight);
--current-line-height: var(--pixel-line-height-relaxed);
--current-text-shadow: var(--pixel-shadow-light);
--current-scale: var(--pixel-scale-large);
```

### 🎮 ゲーム風（Gaming Style）
```css
--current-font-size: var(--pixel-font-size-large);
--current-letter-spacing: var(--pixel-letter-spacing-loose);
--current-line-height: var(--pixel-line-height-compact);
--current-text-shadow: var(--pixel-shadow-heavy);
--current-scale: var(--pixel-scale-huge);
```

## カスタム値の設定 - Custom Values

独自の値を設定したい場合は、直接数値を指定できます：

```css
--current-font-size: 12px;           /* カスタムフォントサイズ */
--current-letter-spacing: 1.5px;     /* カスタム文字間隔 */
--current-line-height: 1.3;          /* カスタム行間 */
--current-text-shadow: 2px 2px 0px #666666;  /* カスタムシャドウ */
--current-scale: 1.15;               /* カスタムスケール */
```

## 変更の反映 - Applying Changes

1. `style-retro.css` の45-49行目を編集
2. ファイルを保存
3. ブラウザでページをリフレッシュ
4. 変更が即座に反映されます！

## 注意点 - Notes

- `--current-scale` を大きくしすぎると、レイアウトが崩れる可能性があります
- モバイルデバイスでは小さいフォントサイズは読みにくくなる場合があります
- 極端な設定は可読性を損なう可能性があるため、テストしながら調整してください