/** Content ownership is global; company/personnel operations keep their scope. */
export function canEditRemoteContent(user) {
  return user?.role === 'global_admin';
}
