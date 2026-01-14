# UI Internationalization Plan

## Overview
Add JavaScript-based i18n to translate UI text into the user's selected language (English, Danish, Dutch). Uses Alpine.js store for instant language switching without page reload.

**Scope (this plan):**
- All UI text except app title and artwork titles/metadata
- Search bar text, buttons, examples, modals, error messages

**Deferred:**
- AI-generated descriptions (caching per language)
- Work type translations

---

## Implementation Approach

### 1. Translation Files
Create JSON files in `/artsearch/static/i18n/`:
- `en.json` - English (base)
- `da.json` - Danish
- `nl.json` - Dutch

Structure:
```json
{
  "nav": { "viewOnGitHub": "View on GitHub" },
  "home": {
    "discoverArt": "Discover art through meaning-driven search!",
    "searchPlaceholder": "Search by theme, style, emotion, or more...",
    "searchButton": "Search",
    "tryExamples": "Try these examples",
    "more": "More",
    "less": "Less"
  },
  "viewer": {
    "findSimilar": "Find similar",
    "tellMeAbout": "Tell me about this artwork",
    "generatingDescription": "Generating description...",
    "aboutThisArtwork": "About this artwork",
    "regenerate": "Regenerate"
  },
  "card": { "findSimilar": "Find similar", "score": "Score:" },
  "dropdown": {
    "selectAll": "Select All",
    "allMuseums": "All Museums",
    "museum": "museum",
    "museums": "museums",
    "allWorkTypes": "All Work Types",
    "workType": "Work Type",
    "workTypes": "Work Types",
    "works": "works"
  },
  "response": { "noArtworksMatch": "No artworks match your selected filters." },
  "description": {
    "rateLimitTitle": "Rate limit exceeded",
    "rateLimitMessage": "Too many requests. Please try again in an hour.",
    "aiGenerated": "AI-generated description based on artwork image and available",
    "museumMetadata": "museum metadata",
    "errorMessage": "Unable to generate description at this time. Please try again later."
  },
  "examples": ["Ship in a storm", "Reading child", ...]
}
```

### 2. Alpine.js i18n Store (in base.html)
```javascript
Alpine.store('i18n', {
  lang: localStorage.getItem('searchLang') || 'en',
  translations: {},
  loaded: false,

  async loadTranslations(lang) { /* fetch /static/i18n/{lang}.json */ },
  async setLanguage(lang) { /* update lang, localStorage, load translations */ },
  t(key) { /* return translations[key] with dot notation support */ }
});
```

### 3. Template Translation Pattern
```html
<!-- Before -->
<p>Discover art through meaning-driven search!</p>

<!-- After -->
<p x-text="$store.i18n.t('home.discoverArt')">Discover art through meaning-driven search!</p>
```

Keep English text inline as fallback while translations load.

### 4. Example Queries
Move from server-rendered to Alpine-rendered using `x-for` over `$store.i18n.translations.examples`.

### 5. Dropdown Pluralization
Update `dropdownComponent` to use i18n store for labels like "1 museum" vs "3 museums".

---

## Files to Modify

| File | Changes |
|------|---------|
| `artsearch/static/i18n/en.json` | **NEW** - English translations |
| `artsearch/static/i18n/da.json` | **NEW** - Danish translations |
| `artsearch/static/i18n/nl.json` | **NEW** - Dutch translations |
| `artsearch/templates/base.html` | Add i18n store init, translate nav |
| `artsearch/templates/home.html` | Connect language selector to store, translate all text, refactor examples |
| `artsearch/templates/partials/dropdown.html` | Update component for i18n labels |
| `artsearch/templates/partials/artwork_card.html` | Translate "Find similar", "Score:" |
| `artsearch/templates/partials/artwork_response.html` | Translate empty state message |
| `artsearch/templates/partials/artwork_description.html` | Translate error messages, AI disclaimer |

---

## Implementation Order

1. Create translation JSON files (en.json, da.json, nl.json)
2. Add i18n store to base.html
3. Update language selector in home.html to use store
4. Translate home.html static text
5. Refactor example queries to use translations
6. Update dropdown.html for i18n
7. Update HTMX partials (artwork_card, artwork_response, artwork_description)
8. Test all languages and verify HTMX partial injection works

---

## Verification

1. Start dev server: `make develop`
2. Open browser, check default English UI
3. Switch to Danish - verify all UI text changes instantly (no reload)
4. Switch to Dutch - verify all UI text changes
5. Perform a search - verify HTMX-loaded cards show translated text
6. Click an artwork - verify modal text is translated
7. Test "Find similar" and "Tell me about this artwork" buttons
8. Verify example queries update per language
9. Check dropdown labels show correct singular/plural forms
10. Refresh page - verify language persists from localStorage
