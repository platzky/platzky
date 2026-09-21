describe('Footer', () => {
  it('shows the site-wide footer in the current language', () => {
    cy.visit('/blog/')
    cy.get('#footer-row').should('contain.text', 'English footer')
    cy.get('#footer-row a[href="/blog/"]').should('exist')

    cy.get('#languages-menu').click()
    cy.contains('.dropdown-item', 'polski').click()

    cy.get('#footer-row').should('contain.text', 'Polska stopka')
  })

  it('collapses and expands when its toggle is clicked', () => {
    cy.visit('/blog/')
    // The labels are visually hidden for screen readers, so check which one is displayed.
    cy.get('#footer-row details').should('have.attr', 'open')
    cy.get('#footer-row .footer-toggle-hide').should('not.have.css', 'display', 'none')
    cy.get('#footer-row .footer-toggle-show').should('have.css', 'display', 'none')

    cy.get('#footer-row summary').click()
    cy.get('#footer-row details').should('not.have.attr', 'open')
    cy.get('#footer-row .footer-toggle-hide').should('have.css', 'display', 'none')
    cy.get('#footer-row .footer-toggle-show').should('not.have.css', 'display', 'none')

    cy.get('#footer-row summary').click()
    cy.get('#footer-row details').should('have.attr', 'open')
  })
})
