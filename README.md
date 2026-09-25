# VEXA

Online store for VEXA, a technology shop in Kigali: CCTV, laptops, networking, air conditioning, fire safety and accessories, with delivery and installation across Rwanda.

Built with [Eleventy](https://www.11ty.dev/). Orders are sent to the sales team on WhatsApp; nothing is charged online.

## Run it

```bash
npm install
npx @11ty/eleventy --serve
```

The site builds into `_site/` (`npx @11ty/eleventy`), which is what gets deployed.

## Where things live

- `src/_data/catalog.json`: every product and department (prices in RWF, photo, description).
- `src/_data/site.js`: phone, WhatsApp, email, founder details.
- `src/_data/photoCredits.json`: credits for the openly licensed photos, shown on `/photo-credits/`.
- `scripts/import_new_products.py`: adds rows from the "New products" sheet of the price/stock spreadsheet, and updates prices (`--update-prices`, `--hold ROW`).
- `scripts/hero-video/render_door.py`: renders the home page hero video into `src/assets/video/`.

Stock quantities from the spreadsheet are never published on the site.
