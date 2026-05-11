describe('Example plugins', () => {
  it('red_letter: [red] shortcode wraps content in a red span', () => {
    cy.visit('/blog/red-test')
    cy.get('span[style="color:red"]').first().should('contain.text', 'danger')
  })

  it('red_letter: letter "a" is wrapped in a red span', () => {
    cy.visit('/blog/red-test')
    cy.get('span[style="color:red"]').should('have.length', 2)
    cy.get('span[style="color:red"]').last().should('have.text', 'a')
  })
})
