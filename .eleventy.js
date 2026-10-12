module.exports = function(eleventyConfig) {
  eleventyConfig.addPassthroughCopy("src/assets");
  eleventyConfig.addWatchTarget("src/");

  // Linked product photos (manufacturer sites) go through Netlify's Image CDN on the live site:
  // fetched once, resized to the width the page needs, converted to WebP/AVIF and cached.
  // Local builds keep the original link. Allowed hosts are listed in netlify.toml [images].
  // Hikvision refuses non-browser fetches and its photos are already small, so they stay direct links.
  const onNetlify = Boolean(process.env.NETLIFY);
  const directHosts = /^https?:\/\/assets\.hikvision\.com\//;
  eleventyConfig.addFilter("imgsrc", (url, width) => {
    if (!url || !/^https?:\/\//.test(url) || !onNetlify || directHosts.test(url)) return url;
    return `/.netlify/images?url=${encodeURIComponent(url)}&w=${width || 600}&q=78`;
  });

  // 1250000 -> "RWF 1,250,000"; missing prices read as a quote request
  eleventyConfig.addFilter("rwf", (amount) => {
    if (typeof amount !== "number" || !Number.isFinite(amount) || amount <= 0) {
      return "Price on request";
    }
    return "RWF " + Math.round(amount).toLocaleString("en-US");
  });

  eleventyConfig.addFilter("where", (items, key, value) => (items || []).filter(item => item[key] === value));
  eleventyConfig.addFilter("featured", (items) => (items || []).filter(item => item.featured));
  eleventyConfig.addFilter("withPhoto", (items) => (items || []).filter(item => item.img));
  eleventyConfig.addFilter("take", (items, n) => (items || []).slice(0, n));
  eleventyConfig.addFilter("findBy", (items, key, value) => (items || []).find(item => item[key] === value));
  eleventyConfig.addFilter("uniq", (items, key) => [...new Set((items || []).map(item => item[key]).filter(Boolean))].sort());

  // Same aisle first, then the rest of the department
  eleventyConfig.addFilter("related", (items, product, n) => {
    const others = (items || []).filter(item => item.slug !== product.slug && item.category === product.category);
    const sameAisle = others.filter(item => item.aisle === product.aisle);
    const rest = others.filter(item => item.aisle !== product.aisle);
    return [...sameAisle, ...rest].slice(0, n);
  });

  // Stable store reference shown on product pages and orders. Products carry their own sku so
  // removing one never renumbers the rest; anything added without one continues after the highest.
  eleventyConfig.addFilter("sku", (items, product) => {
    if (product.sku) return product.sku;
    const list = items || [];
    const top = Math.max(1000, ...list.map(item => parseInt(String(item.sku || "").slice(3), 10) || 0));
    return "VX-" + String(top + 1 + list.filter(item => !item.sku).indexOf(product));
  });

  return {
    dir: {
      input: "src",
      output: "_site",
      includes: "_includes",
      layouts: "_layouts",
      data: "_data"
    },
    templateFormats: ["html", "njk", "md"],
    htmlTemplateEngine: "njk",
    markdownTemplateEngine: "njk"
  };
};
