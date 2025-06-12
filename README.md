# Semantic Art Search 🎨🔍

**Explore Art Through Meaning-Driven Search.**

[Semantic Art Search](https://semantic-art-search.com) is an open-source search engine that helps you discover artworks from public, digitized collections in an intuitive and flexible way. Using advanced machine learning behind the scenes, it allows you to search for pieces based on themes, motifs, emotions, styles, and more. It also allows you to find visually or thematically similar works across multiple museums.

Currently, the system includes selected artworks from:

- Statens Museum for Kunst (The Danish National Gallery)
- Cleveland Museum of Art
- Rijksmuseum Amsterdam

---

## 🔎 How It Works

Just use the search bar — it's designed for natural language input. Try a theme, mood, style, or description:
- *"Mourning"*
- *"Battle at sea"*
- *"Impressionism"*
- *"Bible scene"*

You can also paste an inventory number (e.g., *"KMS1"*) into the search bar to find visually or thematically related works. This is especially useful when clicking “Find similar” on a specific artwork.

When you search:
- The entire collection is ranked by relevance (best matches are shown first)
- You can filter by work type (e.g., painting, print, drawing)
- You can search across all museums or limit to one or more

Each artwork links to its page at the source museum, so you can dive deeper and explore the full context

Currently, **search queries must be in English**, but multilingual support might be added in a future version.

---

## 🤔 How Is This Search Different?

Traditional art search engines often rely on *exact keyword matches* in stored metadata such as titles, descriptions, and tags. If you search for "cat", such engines will return artworks that explicitly mention "cat" in their metadata. While this kind of search has its merits, it also has clear limitations. For example, a painting might depict a cat without mentioning it in the title or description, or the title might contain the word "cat" in another language. In these cases, you would get no results, even though the painting is relevant to your search.

Semantic Art Search helps you discover works that match the intent of your query by disregarding the metadata and instead finding meaning *directly in the image*. If there's a cat somewhere in the painting, there's a good chance that this work will be found, even if the word "cat" does not appear in the metadata. Being natural language based, the semantic search engine also understands abstract concepts and phrases like "war", "ancient Rome", or "shipwreck in a storm", allowing you to search in a very flexible and intuitive way.

> 📝 *Note: Filters such as work type and museum still use metadata — but search relevance is driven by visual and semantic similarity.*

---

## 🧠 Behind The Scenes

The system uses *CLIP*, a multimodal neural network, to embed both images and search queries into a shared vector space. It then performs vector-based nearest neighbor search to rank artworks by semantic or stylistic relevance to the query.

## 🎨 Artwork Coverage

The system includes artworks that:
- Are in the *public domain*
- Have a photograph available in the museum dataset

Not all types of artworks are yet included - focus for now is on visual art like paintings, prints, and drawings. Coverage will grow over time.

---

## 🙌 Acknowledgments

This project is made possible by the excellent **open data initiatives** of:

- [Statens Museum for Kunst](https://open.smk.dk)
- [Cleveland Museum of Art](https://www.clevelandart.org)
- [Rijksmuseum](https://www.rijksmuseum.nl/en/collection)

---

## 📬 Get in Touch

Have questions, feedback, or ideas? Want to contribute?

Reach out via:
- **Email**: [kmollerschmidt@gmail.com](mailto:kmollerschmidt@gmail.com)
- **LinkedIn**: [Kristian Møller Schmidt](https://www.linkedin.com/in/kristian-m%C3%B8ller-schmidt-516b9170/)
