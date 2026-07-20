const tsPlugin = require("@typescript-eslint/eslint-plugin");
const tsParser = require("@typescript-eslint/parser");

// try to import recommended configs if available
let tsRecommended = { rules: {} };
let nextRecommended = { rules: {} };
try {
  tsRecommended = tsPlugin.configs && tsPlugin.configs.recommended ? tsPlugin.configs.recommended : tsRecommended;
} catch (e) {}
try {
  const nextCfg = require("eslint-config-next");
  nextRecommended = (nextCfg && nextCfg.configs && nextCfg.configs.recommended) ? nextCfg.configs.recommended : (nextCfg || nextRecommended);
} catch (e) {}

module.exports = [
  {
    ignores: ["node_modules/**", ".next/**"],
  },
  {
    files: ["**/*.{js,jsx,ts,tsx}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: { "@typescript-eslint": tsPlugin },
    rules: {
      // start from recommended next + typescript rules, then project-specific overrides
      ...(nextRecommended.rules || {}),
      ...(tsRecommended.rules || {}),
      "no-unused-vars": "warn",
    },
  },
];
