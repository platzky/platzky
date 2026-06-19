describe('Language switcher', () => {
  it('changes the displayed language when a different option is selected', () => {
    cy.visit('/blog/')
    cy.get('#languages-menu').should('contain.text', 'en')
    cy.contains('.nav-link', 'Home')

    cy.get('#languages-menu').click()
    cy.contains('.dropdown-item', 'polski').click()

    cy.get('#languages-menu').should('contain.text', 'pl')
    cy.contains('.nav-link', 'Strona domowa')
  })
})
