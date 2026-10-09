/* Internal native signature helpers; sound candidate filtering only. GPL-2.0-or-later. */
#pragma once
#include "fsearch_headless.h"
#include "fsearch_utf.h"
#include <stdint.h>
#include <string.h>
#include <unicode/ustring.h>
#define SIGNATURE_MAX_BYTES (256u * 1024u * 1024u)
#define CANDIDATE_BLOCK_BUDGET 500000u
#define SIGNATURE_NONASCII (UINT64_C(1) << 63)
#define SIGNATURE_UPPERCASE (UINT64_C(1) << 62)
#define SIGNATURE_WORDS 3u
#define SIGNATURE_BITS (SIGNATURE_WORDS * 64u - 2u)
#define SIGNATURE_GRAMS (SIGNATURE_UPPERCASE - 1)
static unsigned signature_lower(unsigned c) { return c >= 'A' && c <= 'Z' ? c + 32 : c; }
static bool signature_ascii(const char *name) {
    for (const unsigned char *p = (const unsigned char *)name; *p; ++p) if (*p >= 128) return false;
    return true;
}
static void signature_text(const char *name, uint64_t out[SIGNATURE_WORDS]) {
    memset(out, 0, SIGNATURE_WORDS * sizeof(uint64_t));
    if (!signature_ascii(name)) out[SIGNATURE_WORDS-1] |= SIGNATURE_NONASCII;
    size_t length = strlen(name);
    for (size_t i = 0; i < length; ++i)
        if (name[i] >= 'A' && name[i] <= 'Z') { out[SIGNATURE_WORDS-1] |= SIGNATURE_UPPERCASE; break; }
    for (size_t i = 0; i + 2 < length; ++i) {
        uint32_t gram = (signature_lower((unsigned char)name[i]) << 16)
                      | (signature_lower((unsigned char)name[i+1]) << 8)
                      | signature_lower((unsigned char)name[i+2]);
        uint32_t hash = gram;
        hash ^= hash >> 16; hash *= UINT32_C(0x7feb352d);
        hash ^= hash >> 15; hash *= UINT32_C(0x846ca68b); hash ^= hash >> 16;
        unsigned first = hash % SIGNATURE_BITS, second = (hash >> 7) % SIGNATURE_BITS;
        out[first / 64] |= UINT64_C(1) << (first % 64);
        out[second / 64] |= UINT64_C(1) << (second % 64);
    }
}
static bool short_ascii_contains(const char *name, const char *query, bool match_case) {
    unsigned first = match_case ? (unsigned char)query[0] : signature_lower((unsigned char)query[0]);
    unsigned second = match_case ? (unsigned char)query[1] : signature_lower((unsigned char)query[1]);
    for (const unsigned char *p = (const unsigned char *)name; *p; ++p) {
        unsigned c = match_case ? *p : signature_lower(*p);
        if (c == first && (!second || (match_case ? p[1] : signature_lower(p[1])) == second)) return true;
    }
    return false;
}
/* Use the same ICU normalization as the authoritative literal matcher. */
static char *normalized_utf8(FsearchUtfBuilder *builder, const char *text) {
    size_t length = strlen(text);
    if (!builder->initialized || length > (size_t)builder->num_characters / 4) {
        fsearch_utf_builder_clear(builder);
        fsearch_utf_builder_init(builder, MAX(length, 512u));
    }
    if (!fsearch_utf_builder_normalize_and_fold_case(builder, text)) return NULL;
    int32_t capacity = 3 * builder->string_normalized_folded_len + 1;
    char *out = g_try_malloc(capacity);
    if (!out) return NULL;
    UErrorCode status = U_ZERO_ERROR;
    u_strToUTF8(out, capacity, NULL, builder->string_normalized_folded,
                builder->string_normalized_folded_len, &status);
    if (U_FAILURE(status)) { g_free(out); return NULL; }
    return out;
}
static bool query_signature(const Options *options, uint64_t required[SIGNATURE_WORDS]) {
    if (options->path) return false;
    if (signature_ascii(options->query) || options->match_case) {
        if (strlen(options->query) < 3) return false;
        signature_text(options->query, required);
        required[SIGNATURE_WORDS-1] &= ~SIGNATURE_UPPERCASE;
        return true;
    }
    FsearchUtfBuilder builder = {0};
    g_autofree char *normalized = normalized_utf8(&builder, options->query);
    bool result = builder.fold_options == U_FOLD_CASE_DEFAULT
                  && normalized && strlen(normalized) >= 3;
    if (result) {
        signature_text(normalized, required);
        required[SIGNATURE_WORDS-1] &= ~SIGNATURE_UPPERCASE;
    }
    fsearch_utf_builder_clear(&builder);
    return result;
}
