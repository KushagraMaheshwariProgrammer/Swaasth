import assert from "node:assert/strict";
import { hasScrolledToBottom } from "../src/utils/termsScroll.js";

function createElement({
  scrollHeight,
  clientHeight,
  scrollTop,
}) {
  return {
    scrollHeight,
    clientHeight,
    scrollTop,
  };
}

assert.equal(
  hasScrolledToBottom(createElement({ scrollHeight: 400, clientHeight: 400, scrollTop: 0 })),
  true,
  "short content should count as scrolled"
);

assert.equal(
  hasScrolledToBottom(createElement({ scrollHeight: 1000, clientHeight: 400, scrollTop: 0 })),
  false,
  "top of long content should not count as scrolled"
);

assert.equal(
  hasScrolledToBottom(createElement({ scrollHeight: 1000, clientHeight: 400, scrollTop: 600 })),
  true,
  "bottom of long content should count as scrolled"
);

assert.equal(hasScrolledToBottom(null), false, "missing element should be false");

console.log("termsScroll tests passed");
