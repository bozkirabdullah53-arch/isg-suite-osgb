import js from "@eslint/js";
import globals from "globals";

/** P1-09: kademeli lint — auth / legal / memberships / api / validation / offline / duty / legal_docs. */
export default [
  {ignores: ["dist/**", "node_modules/**", "e2e/**"]},
  {
    files: [
      "src/auth_session.js",
      "src/legal_acceptances.jsx",
      "src/memberships_panel.jsx",
      "src/api.js",
      "src/validation.js",
      "src/field_offline.js",
      "src/duty_dashboard.jsx",
      "src/legal_docs.jsx",
      "src/training_question_bank_logic.js",
      "src/training_question_bank_logic.test.js",
      "src/authorized_firm*.js",
      "src/authorized_firm*.jsx",
      "src/personnel_profile*.js",
      "src/personnel_profile*.jsx",
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
  {
    files: ["src/authorized_firms.jsx"],
    rules: {
      // Core ESLint JSX identifiersini kullanım olarak işaretlemez; Vite build
      // ve no-undef kontrolü bu dosyada etkin kalır.
      "no-unused-vars": "off",
    },
  },
];
