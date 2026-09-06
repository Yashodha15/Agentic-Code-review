import { useEffect, useState } from 'react';

export function AccountSearch({ accountId }: { accountId: string }) {
  const [name, setName] = useState('');

  useEffect(() => {
    fetch(`/api/accounts/${accountId}`)
      .then((response) => response.json())
      .then((account) => setName(account.name));
  }, []);

  return <strong>{name}</strong>;
}
