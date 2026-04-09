"""
A doubly linked list implementation.

Fixes:
- link_nodes now handles None values for node1/node2 (so you can link at head/tail).
- link_nodes updates the list's head and tail when linking nodes at boundaries.
- add_node ensures the new node's prev/next are correct and keeps head/tail consistent.
- traverse still returns Node objects in order from head to tail.

"""

class Node:
    def __init__(self, data):
        self.data = data
        self.prev = None
        self.next = None

class DoublyLinkedListFixed:
    def __init__(self):
        self.head = None
        self.tail = None

    def add_node(self, data):
        new_node = Node(data)
        # Ensure the new node is a clean standalone node for defence programming (prev/next should be None)
        new_node.prev = None
        new_node.next = None

        if not self.head:
            # empty list
            self.head = new_node
            self.tail = new_node
        else:
            # attach to current tail
            self.tail.next = new_node
            new_node.prev = self.tail
            self.tail = new_node
        return new_node

    def link_nodes(self, node1, node2):
        """
        Link node1 -> node2 (i.e., set node1.next = node2 and node2.prev = node1).
        Handles node1 or node2 being None to allow linking at head or tail:
         - node1 is None: node2 becomes the head (node2.prev set to None)
         - node2 is None: node1 becomes the tail (node1.next set to None)
        Also updates self.head and self.tail as appropriate.
        """
        # If both are None nothing to do
        if node1 is None and node2 is None:
            return

        # Link node1 -> node2
        if node1 is None:
            # Setting a new head
            if node2 is not None:
                node2.prev = None
                self.head = node2
                # If list had no tail, make node2 the tail as well (find end)
                if self.tail is None:
                    # find tail by walking next pointers from node2
                    cur = node2
                    while cur.next:
                        cur = cur.next
                    self.tail = cur
        else:
            # set node1.next to node2
            node1.next = node2
            # if node1 was previously the tail and now points to a next, update tail if needed
            if self.tail is node1 and node2 is not None:
                # node2 or its downstream node becomes new tail if node2.next is None else tail will be found later
                if node2.next is None:
                    self.tail = node2
                else:
                    # find tail by walking from node2
                    cur = node2
                    while cur.next:
                        cur = cur.next
                    self.tail = cur

        if node2 is None:
            # Setting a new tail
            if node1 is not None:
                node1.next = None
                self.tail = node1
                if self.head is None:
                    # find head by walking prev pointers from node1
                    cur = node1
                    while cur.prev:
                        cur = cur.prev
                    self.head = cur
        else:
            # set node2.prev to node1
            node2.prev = node1
            # if list had no head, set it
            if self.head is None:
                if node1 is None:
                    self.head = node2
                else:
                    # find head by walking prev pointers from node1
                    cur = node1
                    while cur.prev:
                        cur = cur.prev
                    self.head = cur

    def traverse(self):
        """Return list of nodes from head to tail."""
        visited = []
        current = self.head
        while current:
            visited.append(current)
            current = current.next
        return visited
