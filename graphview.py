import sys

import networkx as nx
import gravis as gv
import brainstormer_p2


if __name__ == '__main__':

    g = nx.DiGraph()
    g.graph['node_label_size'] = 6
    g.graph['node_label_color'] = 'grey'
    colors = ['red', 'grey', 'green']
    model = brainstormer_p2.Model()
    model.read_from_file(sys.argv[1])

    for post in model.time_ordered:
        label = post.text if len(post.text) <= 30 else post.text[:27] + "..."
        if post.auxiliary == -1:
            label = "[-] "+label
        elif post.auxiliary == 1:
            label = "[+] "+label
        g.add_node(post.ident, label=label, color=colors[post.formality() + 1])
        if post.parent is not None:
            g.add_edge(post.parent.ident, post.ident, color='black')
        if post.destination is not None:
            g.add_edge(post.ident, post.destination.ident, color='magenta')

    fig = gv.d3(g, node_label_data_source='label')
    fig.display()
