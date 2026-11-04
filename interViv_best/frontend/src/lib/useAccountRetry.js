import { useCallback, useState } from 'react';
import { accountLoadAction } from './requestErrors.js';

/**
 * Account-load failures keep the page (overhaul Phase 4). Only a confirmed
 * expiry signs the user out, and lib/api.js does that centrally; aborted
 * requests are ignored and every other failure offers "Try again".
 */
export function useAccountRetry() {
  const [accountError, setAccountError] = useState('');
  const [accountAttempt, setAccountAttempt] = useState(0);
  const retryAccount = useCallback(() => {
    setAccountError('');
    setAccountAttempt((n) => n + 1);
  }, []);
  const onAccountError = useCallback((err) => {
    const action = accountLoadAction(err);
    if (action === 'ignore') return;
    setAccountError(
      action === 'signin'
        ? 'Your sign-in could not be confirmed. Try again, or sign in again.'
        : (err?.message || 'Could not load your account.'),
    );
  }, []);
  return { accountError, accountAttempt, retryAccount, onAccountError };
}
