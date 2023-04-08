import Login from './login.js'
import Menu from './menu.js'

export default {
    data() {
        return {
            'characterName': '',
            'server': '',
            'servers': {},
            'serverNames': [],
            'minimumRun': 1,
            'players': new vis.DataSet([]),
            'relations': new vis.DataSet([]),
            'nextId': 1,
            'showOption': true,
        }
    },
    components: {
        Login, Menu
    },
    methods: {
        search() {
            if (this.characterName == '') {
                return;
            }
            this.characterName = this.characterName.substring(0, 1).toUpperCase() +
                this.characterName.substring(1).toLowerCase();
            
            if (window.localStorage) {
                window.localStorage.setItem('relation_server', this.server);
                window.localStorage.setItem('relation_character', this.characterName);
                window.localStorage.setItem('relation_run', this.minimumRun);
            }

            fetch('char/relation/' + encodeURI(this.server) + '/' + encodeURI(this.characterName) + '/' + this.minimumRun).then(async resp => {
                const data = await resp.json();
                let i1 = this.players.get().find(p => p.label == this.characterName + '-' + this.server);
                if (i1 === undefined) {
                    i1 = {
                        id: this.nextId++,
                        label: this.characterName + '-' + this.server
                    };
                    this.players.add(i1);
                }

                data.forEach(dd => {
                    if (dd.value >= this.minimumRun) {
                        let i2 = this.players.get().find(p => p.label == dd.name + '-' + dd.realm);
                        if (i2 === undefined) {
                            i2 = {
                                id: this.nextId++,
                                label: dd.name + '-' + dd.realm
                            };
                            this.players.add(i2);
                        }
                        
                        var exists = this.relations.get().some(rel => (rel.from == i1.id && rel.to == i2.id) || (rel.from == i2.id && rel.to == i1.id));
                        // this.relations.forEach(rel => {
                        //     if (rel.from == i1.id && rel.to == i2.id) {
                        //         exists = true
                        //     } else if (rel.from == i2.id && rel.to == i1.id) {
                        //         exists = true
                        //     }
                        // })
                        if (!exists) {
                            this.relations.add({from: i1.id, to: i2.id, value: dd.value, title: dd.value })
                        }
                    }
                })
            })
        },
    },
    beforeMount() {
        if (window.localStorage) {
            const server = window.localStorage.getItem('relation_server')
            const run = parseInt(window.localStorage.getItem('relation_run'))
            this.server = server
            this.characterName = window.localStorage.getItem('relation_character')
            if (run > 0) {
                this.minimumRun = run
            }
        }
    },
    mounted() {
        fetch('form/realms').then(async resp => {
            this.servers = await resp.json()
            for (var key in this.servers) {
                this.serverNames.push(this.servers[key]);
                // {
                //     "label": this.servers[key],
                //     "value": this.servers[key],
                // })
            }
            if (this.server == '') {
                this.server = this.serverNames[0]['value']
            }
        })

        var container = document.getElementById('relations')
        var data = {
            nodes: this.players,
            edges: this.relations
        }
        var options = {}
        var network = new vis.Network(container, data, options)
        network.on('doubleClick', e => {
            if (e.nodes.length > 0) {
                var id = e.nodes[0];
                var pl = this.players.get().find(p => p.id == id);
                var name = pl.label;
                this.server = name.substring(name.indexOf('-') + 1);
                this.characterName = name.substring(0, name.indexOf('-'));
                this.search();
            }
        })
    },
    template: `
    <v-container fluid>
        <v-row v-if="showOption" no-gutters>
            <v-col cols="12" sm="5">
                <v-text-field type="text" label="캐릭터명" v-model="characterName" />
            </v-col>
            <v-col cols="12" sm="4">
                <v-combobox id="server" label="서버" :items="serverNames" v-model="server" />
            </v-col>
            <v-col cols="12" sm="3">
                <v-text-field type="number" label="최소 파티횟수" v-model="minimumRun" min="1" max="10000" ></v-text-field>
            </v-col>
        </v-row>
        <v-row no-gutters>
            <v-col>
                <v-btn class="ma-1" variant="outlined" @click="search">검색</v-btn>
                <v-btn class="ma-1" variant="outlined" @click="showOption=!showOption">{{ showOption ? "검색 조건 닫기" : "검색 조건 열기" }}</v-btn>
                <Menu/>
                <Login/>
            </v-col>
        </v-row>
        <v-row no-gutters style="background-color: #f0f0f0">
            <v-col>
                <div id="relations" style="height: calc(100vh - 100px)"></div>
            </v-col>
        </v-row>
    </v-container>
    `,
}
