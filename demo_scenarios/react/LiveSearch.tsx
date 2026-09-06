import { useEffect, useState } from "react";

export function LiveSearch({ query }: { query: string }) {
  const [results, setResults] = useState<string[]>([]);

  useEffect(() => {
    fetch(`/api/search?q=${query}`)
      .then((response) => response.json())
      .then(setResults);
  }, []);

  return <ul>{results.map((result) => <li>{result}</li>)}</ul>;
}

