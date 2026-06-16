import assert from "node:assert/strict";
import { TERMS_VERSION } from "../src/data/termsAndConditions.js";
import {
  clearLocalTermsAcceptance,
  getLocalTermsAcceptance,
  setLocalTermsAcceptance,
} from "../src/services/localTermsStore.js";

global.localStorage = {
  store: {},
  getItem(key) {
    return this.store[key] ?? null;
  },
  setItem(key, value) {
    this.store[key] = value;
  },
  removeItem(key) {
    delete this.store[key];
  },
};

const userId = "test-user-123";

assert.equal(getLocalTermsAcceptance(userId).accepted, false);

setLocalTermsAcceptance(userId);
const accepted = getLocalTermsAcceptance(userId);
assert.equal(accepted.accepted, true);
assert.equal(accepted.version, TERMS_VERSION);

clearLocalTermsAcceptance(userId);
assert.equal(getLocalTermsAcceptance(userId).accepted, false);

console.log("localTermsStore tests passed");
