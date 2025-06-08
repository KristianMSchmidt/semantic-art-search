# Semantic Art Search 🎨🔍

**Explore art through meaning — not just keywords.**

[Semantic Art Search](https://semantic-art-search.com) is an open-source search engine that helps you discover artworks based on **visual and semantic similarity**, not just titles or tags.

Using machine learning, it lets you:
- Search by natural language (e.g., *"ancient ruins"*, *"mourning"*, *"moonlight"*)
- Jump from any artwork to similar pieces — even across museums
- Explore themes, styles, and visual connections in a more intuitive way

Unlike traditional search tools, results are ranked by **how closely artworks match your intent**, not how well they match metadata.

Currently, the system includes selected artworks from:
- **Statens Museum for Kunst** (The Danish National Gallery)
- **Cleveland Museum of Art**
- **Rijksmuseum Amsterdam**

---

## 🔎 How It Works

Just use the **search bar** — it's designed for natural language input. Try a theme, mood, style, or description:
- *"Sorrow"*
- *"Portrait with flowers"*
- *"Battle at sea"*

You can also paste an artwork **inventory number** (e.g., *KMS1*) to find **visually or thematically related works**. This is especially useful when clicking **“Find similar”** on a specific artwork.

When you search:
- The **entire collection** is ranked by relevance
- You can **filter by work type** (e.g., painting, print, drawing)
- You can **search across all museums** or limit to one

> 📝 *Filters use metadata, but the actual search ranking is based on visual and semantic similarity.*

---

## 🤔 Why Not Just Use Metadata?

Metadata can be incomplete — what you're looking for might not appear in the title or description, or these could be stored in a different language (e.g. Danish or Dutch). Semantic Art Search helps you discover works that match the intent of your query by finding meaning directly **in the image**. 

For example:
- Searching *"Shipwreck in a storm"* can find turbulent seascapes, even if that exact phrase doesn’t appear in the metadata.
- Searching *"Rembrandt"* brings up artworks painted by Rembrandt, in his style, or even portraits of people who resemble him — across multiple collections.

---

## 🌍 What You Can Do

- **Cross-collection comparisons**  
  → What’s the most similar piece in the Rijksmuseum to your favorite SMK painting?

- **Explore moods and motifs**  
  → Search *"battle scenes"*, *"sadness"*, or *"moonlight by the sea"* to browse theme-based clusters.

- **Follow visual trails**  
  → Use **“Find similar”** to dive deeper from any individual artwork.

---

## 🧠 Behind the Scenes

The system uses **CLIP**, a multimodal neural network, to embed both images and search queries into a shared vector space. It then performs **vector-based nearest neighbor search** to return the most semantically relevant artworks.

This means:
- The search engine "understands" visual style and meaning, not just keywords.
- Results are based on similarity in visual or conceptual content, not labels.

All queries return results sorted by **semantic distance**, not keyword match.

Currently, **search queries must be in English**, but multilingual support is possible in the future.

---

## 🎨 Artwork Coverage

The system includes artworks that:
- Are in the **public domain**
- Have a **photograph available** in the museum dataset

Not every object is indexed — focus is on visual artworks like paintings, prints, and drawings. Coverage will grow over time.

---

## 🙌 Acknowledgments

Made possible by the excellent **open data initiatives** of:

- [Statens Museum for Kunst](https://open.smk.dk)
- [Cleveland Museum of Art](https://www.clevelandart.org)
- [Rijksmuseum](https://www.rijksmuseum.nl/en/collection)

---

## 📬 Get in Touch

Have questions, feedback, or ideas? Want to contribute?

Reach out via:
- **Email**: [kmollerschmidt@gmail.com](mailto:kmollerschmidt@gmail.com)  
- **LinkedIn**: [Kristian Møller Schmidt](https://www.linkedin.com/in/kristian-m%C3%B8ller-schmidt-516b9170/)
