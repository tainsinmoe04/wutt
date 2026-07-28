const assert = require('node:assert/strict');
const {
  createEmptyWardrobeDraft,
  wardrobeImageUrlFromApi,
} = require('../wardrobe-utils.js');

const firstDraft = createEmptyWardrobeDraft('Top');
firstDraft.color = 'Navy';
firstDraft.description = 'Relaxed linen shirt';
firstDraft.styleTags = 'minimal';

const nextDraft = createEmptyWardrobeDraft('Shoes');

assert.deepEqual(nextDraft, {
  category: 'Shoes',
  subtype: '',
  color: '',
  description: '',
  styleTags: '',
  occasionTags: '',
  material: '',
  brand: '',
  formalityLevel: '',
  seasonSuitability: '',
});
assert.notEqual(nextDraft, firstDraft);
assert.equal(
  wardrobeImageUrlFromApi({
    cloudinary_url: 'https://images.example/saved-item.jpg',
  }),
  'https://images.example/saved-item.jpg',
);

console.log('wardrobe-utils: metadata reset and image mapping passed');
