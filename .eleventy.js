module.exports = function(eleventyConfig) {
  eleventyConfig.addPassthroughCopy("src/assets");
  eleventyConfig.addWatchTarget("src/");

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

  // Stable store reference shown on product pages and orders
  eleventyConfig.addFilter("sku", (items, product) => "VX-" + String((items || []).indexOf(product) + 1001));

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
