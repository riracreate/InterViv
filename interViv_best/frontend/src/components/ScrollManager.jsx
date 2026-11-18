import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

/** Route changes start at the top; target links wait for account data to render. */
export default function ScrollManager() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (!hash) {
      window.scrollTo(0, 0);
      return undefined;
    }
    let observer;
    let timer;
    const scrollToTarget = () => {
      let id;
      try { id = decodeURIComponent(hash.slice(1)); } catch { return false; }
      const target = document.getElementById(id);
      if (!target) return false;
      target.scrollIntoView();
      observer?.disconnect();
      clearTimeout(timer);
      return true;
    };
    if (!scrollToTarget()) {
      observer = new MutationObserver(scrollToTarget);
      observer.observe(document.body, { childList: true, subtree: true });
      timer = setTimeout(() => observer.disconnect(), 5000);
    }
    return () => { observer?.disconnect(); clearTimeout(timer); };
  }, [pathname, hash]);
  return null;
}
