export async function getOverview(days) {
  const res = await fetch(`/api/overview?days=${days}`);
  if (!res.ok) throw new Error(`Server returned ${res.status}`);
  return res.json();
}
