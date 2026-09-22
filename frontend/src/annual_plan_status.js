export function annualPlanStatusWithCompletion(status, completionDate) {
  return completionDate ? 'completed' : status;
}
