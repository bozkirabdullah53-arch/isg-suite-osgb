import js from "@eslint/js";
import globals from "globals";

/** P1-09: kademeli lint — önce auth_session + legal panel. */
export default [
  {ignores: ["dist/**", "node_modules/**"]},
  {
    files: ["src/auth_session.js", "src/legal_acceptances.jsx"],
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
