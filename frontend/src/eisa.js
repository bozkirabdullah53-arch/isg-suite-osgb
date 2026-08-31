// Vite extensionless imports resolve .js before .jsx.
// Re-export the existing EİSA module and override only additive admin pages.
export * from './eisa.jsx';
export { EisaErrorReportsPage } from './eisa_error_reports.jsx';
export { EisaSystemSettingsPage } from './eisa_system_settings_wrapper.jsx';
