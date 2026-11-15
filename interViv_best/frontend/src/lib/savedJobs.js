export function isSavedJob(jobs, job) {
  return jobs.some(item => item.id === job.id && item.provenance === job.provenance);
}

export function toggleSavedJob(jobs, job) {
  return isSavedJob(jobs, job)
    ? jobs.filter(item => item.id !== job.id || item.provenance !== job.provenance)
    : [job, ...jobs];
}
