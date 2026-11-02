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
        if (child.activeFocusOnTab && out.indexOf(child) < 0)
            out.push(child)
        var inner = child.contentItem !== undefined && child.contentItem ? child.contentItem : child
        focusables(inner, out)
    }
    return out
}

function indexOfHeld(all, held) {
    var i
    for (i = 0; i < all.length; i++) {
        if (all[i] === held)
            return i
    }
    var walk = held
    while (walk) {
        for (i = 0; i < all.length; i++) {
            if (all[i] === walk)
                return i
        }
        walk = walk.parent
    }
    return -1
}

function nextItem(roots, step, held) {
    var all = []
    for (var r = 0; r < roots.length; r++)
        focusables(roots[r], all)
    if (all.length === 0)
        return null
    var at = indexOfHeld(all, held)
    var next = at < 0 ? (step > 0 ? 0 : all.length - 1) : (at + step + all.length) % all.length
    return all[next]
}

function take(item, step) {
    if (!item)
        return
    var reason = step > 0 ? Qt.TabFocusReason : Qt.BacktabFocusReason
    var kids = item.children ? item.children : []
    for (var i = 0; i < kids.length; i++) {
        if (kids[i].objectName === "fieldInput" && kids[i].visible && kids[i].enabled) {
            kids[i].forceActiveFocus(reason)
            return
        }
    }
    item.forceActiveFocus(reason)
}
