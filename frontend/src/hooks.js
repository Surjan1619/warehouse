import { useEffect, useState } from 'react';
import { api } from './api';

/**
 * Load a list from the API.
 * Returns the items, a function to reload them, and the load error text.
 * With an empty `path` nothing is loaded (e.g. until the user picks what to show).
 */
export function useList(path) {
  const [items, setItems] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!path) return;
    api(path).then(setItems).catch((err) => setError(err.message));
  }, [path]);

  const reload = async () => {
    if (path) setItems(await api(path));
  };
  return [items, reload, error];
}

/**
 * Run a create / delete request and keep its state for the page:
 * `busy` while it runs, then either `notice` (success) or `error`.
 */
export function useAction() {
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  // conflictText replaces the server message for 409 (duplicate) answers
  const run = async (action, successText, conflictText) => {
    setError('');
    setNotice('');
    setBusy(true);
    try {
      await action();
      setNotice(successText);
      return true;
    } catch (err) {
      setError(err.status === 409 && conflictText ? conflictText : err.message);
      return false;
    } finally {
      setBusy(false);
    }
  };

  return { error, notice, busy, run };
}

// Empty form fields are sent as null; numeric ones as numbers
export const textOrNull = (value) => (value.trim() === '' ? null : value.trim());
export const numberOrNull = (value) => (value === '' ? null : Number(value));
