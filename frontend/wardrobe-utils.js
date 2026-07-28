/* WUTT wardrobe draft helpers — browser global + Node-test compatible. */

function normalizeWardrobeCategory(value) {
  var categoryMap = {
    top: 'Top',
    tops: 'Top',
    pants: 'Bottom',
    bottom: 'Bottom',
    bottoms: 'Bottom',
    dress: 'Dress',
    dresses: 'Dress',
    jacket: 'Outerwear',
    outerwear: 'Outerwear',
    shoes: 'Shoes',
    accessory: 'Accessory',
    accessories: 'Accessory',
  };
  return categoryMap[String(value || '').toLowerCase()] || 'Item';
}

function createEmptyWardrobeDraft(suggestedCategory) {
  return {
    category: normalizeWardrobeCategory(suggestedCategory),
    subtype: '',
    color: '',
    description: '',
    styleTags: '',
    occasionTags: '',
    material: '',
    brand: '',
    formalityLevel: '',
    seasonSuitability: '',
  };
}

function wardrobeImageUrlFromApi(item) {
  return item && typeof item.cloudinary_url === 'string'
    ? item.cloudinary_url
    : '';
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    createEmptyWardrobeDraft: createEmptyWardrobeDraft,
    normalizeWardrobeCategory: normalizeWardrobeCategory,
    wardrobeImageUrlFromApi: wardrobeImageUrlFromApi,
  };
}
