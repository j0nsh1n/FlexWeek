.pragma library

// Tab order for a modal surface. The same walk SheetFrame uses, so overlays
// do not invent a second focus system.

function focusables(item, out) {
    if (!item)
        return out
    var kids = item.children
    for (var i = 0; i < kids.length; i++) {
        var child = kids[i]
        if (!child.visible || !child.enabled)
            continue
        if (child.activeFocusOnTab)
            out.push(child)
        focusables(child.contentItem !== undefined && child.contentItem ? child.contentItem : child, out)
    }
    return out
}

function nextItem(roots, step, held) {
    var all = []
    for (var r = 0; r < roots.length; r++)
        focusables(roots[r], all)
    if (all.length === 0)
        return null
    var at = -1
    for (var i = 0; i < all.length && at < 0; i++) {
        var walk = held
        while (walk && at < 0) {
            if (walk === all[i])
                at = i
            walk = walk.parent
        }
    }
    var next = at < 0 ? (step > 0 ? 0 : all.length - 1) : (at + step + all.length) % all.length
    return all[next]
}
