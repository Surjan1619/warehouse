// Run with: npm test   (Node built-in test runner, no extra packages)
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { SECTIONS, sectionHome, sectionOf, visibleSections } from './navigation.js';

test('a worker does not see the admin section', () => {
  const keys = visibleSections(false).map((s) => s.key);
  assert.deepEqual(keys, ['stock', 'receive', 'issue', 'catalog']);
});

test('an admin sees every section', () => {
  assert.equal(visibleSections(true).length, SECTIONS.length);
});

test('product types are managed only in the admin section', () => {
  assert.equal(sectionOf('/admin/types').key, 'admin');
  assert.ok(sectionOf('/admin/types').adminOnly);
});

test('cutting and issuing goods are in one section, receiving in another', () => {
  assert.equal(sectionOf('/assembly').key, 'issue');
  assert.equal(sectionOf('/cut').key, 'issue');
  assert.equal(sectionOf('/issue').key, 'issue');
  assert.equal(sectionOf('/receive').key, 'receive');
  assert.equal(sectionOf('/receive/products').key, 'receive');
});

test('pages outside the sections have none', () => {
  assert.equal(sectionOf('/home'), null);
  assert.equal(sectionOf('/nowhere'), null);
});

test('a section opens on its first page', () => {
  assert.equal(sectionHome(sectionOf('/products')), '/stock');
  assert.equal(sectionHome(sectionOf('/journal')), '/admin');
});

test('every page belongs to exactly one section', () => {
  const paths = SECTIONS.flatMap((s) => s.pages.map((p) => p.path));
  assert.equal(new Set(paths).size, paths.length);
});
