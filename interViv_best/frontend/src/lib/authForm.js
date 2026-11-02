/** Field-level validation shared by Login and Signup. Returns {} when valid. */
export function validateLoginFields({ email = '', password = '' } = {}) {
  const errors = {};
  if (!email.trim()) errors.email = 'Email is required.';
  else if (!email.includes('@')) errors.email = 'Enter a valid email address.';
  if (!password) errors.password = 'Password is required.';
  return errors;
}

export function validateSignupFields({ name = '', email = '', password = '', confirmPassword = '' } = {}) {
  const errors = {};
  if (!name.trim()) errors.name = 'Name is required.';
  if (!email.trim()) errors.email = 'Email is required.';
  else if (!email.includes('@')) errors.email = 'Enter a valid email address.';
  if (password.length < 8) errors.password = 'Password must be at least 8 characters.';
  else if (!/[A-Za-z]/.test(password) || !/[0-9]/.test(password)) {
    errors.password = 'Password must contain at least one letter and one number.';
  }
  if (password !== confirmPassword) errors.confirmPassword = 'Passwords do not match.';
  return errors;
}

export function hasFieldErrors(errors) {
  return Object.keys(errors || {}).length > 0;
}
