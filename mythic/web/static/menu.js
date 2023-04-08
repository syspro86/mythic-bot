
export default {
    data() {
        return {
            'items': [
                { 'title': '친구 그래프', 'url': 'relation.html' },
                { 'title': '쐐기평점 타임라인', 'url': 'score-timeline.html' },
            ]
        }
    },
    methods: {
        menu_selected(index) {
            location.href = this.items[index].url;
        }
    },
    template: `
    <v-menu>
      <template v-slot:activator="{ props }">
        <v-btn variant="outlined" v-bind="props">이동</v-btn>
      </template>
      <v-list>
        <v-list-item v-for="(item, index) in items" :key="index" :value="index" @click="menu_selected(index)">
          <v-list-item-title>{{ item.title }}</v-list-item-title>
        </v-list-item>
      </v-list>
    </v-menu>
    `
}
