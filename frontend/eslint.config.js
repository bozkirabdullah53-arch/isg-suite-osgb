import js from "@eslint/js";
import globals from "globals";

/** P1-09: kademeli lint — auth / legal / memberships / api / validation. */
export default [
  {ignores: ["dist/**", "node_modules/**", "e2e/**"]},
  {
    files: [
      "src/auth_session.js",
      "src/legal_acceptances.jsx",
      "src/memberships_panel.jsx",
      "src/api.js",
      "src/validation.js",
    ],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: {...globals.browser},
      parserOptions: {ecmaFeatures: {jsx: true}},
    },
    rules: {
      ...js.configs.recommended.rules,
      "no-unused-vars": ["warn", {argsIgnorePattern: "^_", varsIgnorePattern: "^_"}],
      "no-undef": "error",
    },
  },
];
