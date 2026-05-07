const allPosts = $input.all().map(item => ({
  slug: item.json.slug,
  link: item.json.link
})).filter(p => p.slug && p.link);

const nlWords = /\b(van|met|een|het|de|en|voor|uit|bij|op|in|over|door|naar)\b/i;
const numbered = {};
const unnumbered = [];

for (const post of allPosts) {
  const numMatch = post.slug.match(/^(\d+)-/);
  if (numMatch) {
    const num = numMatch[1];
    if (!numbered[num]) numbered[num] = [];
    numbered[num].push(post);
  } else {
    unnumbered.push(post);
  }
}

const result = [];

for (const num of Object.keys(numbered)) {
  const group = numbered[num];
  const en = group.find(p => !nlWords.test(p.slug));
  result.push((en || group[0]).link);
}

const unnumberedEn = unnumbered.filter(p => !nlWords.test(p.slug));
const unnumberedNl = unnumbered.filter(p => nlWords.test(p.slug));

for (const p of unnumberedEn) result.push(p.link);
for (const p of unnumberedNl) {
  const hasEn = unnumberedEn.some(en => {
    const a = en.slug.replace(nlWords, '').replace(/-+/g, '-');
    const b = p.slug.replace(nlWords, '').replace(/-+/g, '-');
    return a.includes(b.substring(0, 6)) || b.includes(a.substring(0, 6));
  });
  if (!hasEn) result.push(p.link);
}

return [...new Set(result)].map(url => ({ json: { recipeUrl: url } }));
