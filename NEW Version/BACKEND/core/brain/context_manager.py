class ContextManager:
	"""Lightweight conversation context buffer."""

	def __init__(self, max_items=20):
		self.max_items = max_items
		self._items = []

	def add(self, role: str, text: str):
		if not text:
			return
		self._items.append({"role": role, "text": text})
		if len(self._items) > self.max_items:
			self._items = self._items[-self.max_items:]

	def get_recent(self):
		return list(self._items)

	def clear(self):
		self._items.clear()