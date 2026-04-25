import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { h, nextTick } from 'vue'
import MenuDropdown from '@/components/common/MenuDropdown.vue'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

describe('MenuDropdown', () => {
  it('toggles the menu and closes after invoking closeDropdown from the slot', async () => {
    const wrapper = mount(MenuDropdown, {
      attachTo: document.body,
      props: {
        label: 'Providers',
      },
      slots: {
        default: ({ closeDropdown }: { closeDropdown: () => void }) =>
          h(
            'button',
            {
              class: 'inner-action',
              onClick: closeDropdown,
            },
            'Close',
          ),
      },
    })

    const dropdownPanel = wrapper.find('.shadow-lg')

    expect(dropdownPanel.isVisible()).toBe(false)

    await wrapper.find('[data-testid="menu-dropdown-trigger"]').trigger('click')
    await nextTick()
    expect(dropdownPanel.isVisible()).toBe(true)

    await wrapper.find('.inner-action').trigger('click')
    await nextTick()
    expect(dropdownPanel.isVisible()).toBe(false)

    wrapper.unmount()
  })

  it('supports opening the menu upward', async () => {
    const wrapper = mount(MenuDropdown, {
      attachTo: document.body,
      props: {
        label: 'Providers',
        menuPlacement: 'top',
      },
      slots: {
        default: () => h('div', 'Option'),
      },
    })

    await wrapper.find('[data-testid="menu-dropdown-trigger"]').trigger('click')
    await nextTick()

    expect(wrapper.find('.shadow-lg').classes()).toContain('bottom-full')
    expect(wrapper.find('.shadow-lg').classes()).toContain('mb-1')

    wrapper.unmount()
  })
})
